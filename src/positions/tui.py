"""Textual TUI for reviewing queued proposals.

Proposals come from the queue (`positions queue`); the TUI never generates
them. Live Wikidata is only touched on accept: the payload is submitted
verbatim to the REST API — a patch to `PATCH /v1/entities/items/{id}`,
whose own `test` pins make the server reject with a 409 if live state
drifted, or a new-item document to `POST /v1/entities/items`. A drifted
patch goes stale instead of editing the wrong thing; any other failure is
shown in the log and the proposal stays pending for another decision.
Terminal states stay in the proposal table as tombstones; the app itself
only touches the database on the main thread.
"""

import json
from pathlib import Path
from typing import ClassVar

from rich.console import Group
from rich.json import JSON
from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.widgets import Footer, Header, RichLog, Static

from . import db as dbmod
from . import proposals, wikidata


class Submitted(Message):
    """The edit was accepted by Wikidata."""

    def __init__(self, proposal_id: int, created_entity: str | None) -> None:
        super().__init__()
        self.proposal_id = proposal_id
        self.created_entity = created_entity  # a create's new QID


class SubmitStale(Message):
    """An accept found changed live state; the proposal went stale."""

    def __init__(self, proposal_id: int, reason: str) -> None:
        super().__init__()
        self.proposal_id = proposal_id
        self.reason = reason


class SubmitFailed(Message):
    """The edit failed; the proposal stays pending so the human can retry."""

    def __init__(self, proposal_id: int, reason: str) -> None:
        super().__init__()
        self.proposal_id = proposal_id
        self.reason = reason


def render_proposal(p: dbmod.Proposal) -> Group:
    """The proposal exactly as it will be sent: header, raw payload, metadata."""
    parts: list = [
        Text.from_markup(f"[bold]{dbmod.display_name(p)}[/] — {p.comment}"),
        JSON(json.dumps(p.payload)),
    ]
    footer = [f"rationale: {p.rationale}"] if p.rationale else []
    footer += [f"source: {source}" for source in p.sources]
    if footer:
        parts.append(Text.from_markup("\n".join(footer)))
    return Group(*parts)


class PositionsApp(App):
    """Review loop over the live pending-proposal queue."""

    TITLE = "positions"
    CSS = """
    #proposal {
        height: auto;
        margin: 1 2 0 2;
        padding: 1 2;
        border: round $primary;
    }
    #status {
        height: 1;
        padding: 0 3;
        color: $text-muted;
    }
    RichLog {
        height: 1fr;
        margin: 1 2;
        padding: 0 1;
        border: round $secondary;
    }
    """
    BINDINGS: ClassVar = [
        Binding("a", "accept", "Accept"),
        Binding("d", "discard", "Discard"),
        Binding("r", "refresh", "Refresh"),
        Binding("q", "request_quit", "Quit"),
    ]

    def __init__(self, db_path: Path) -> None:
        super().__init__()
        self.db_path = db_path
        self.session: dbmod.Session | None = None
        self.busy = False  # a submission is in flight

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(id="proposal")
        yield Static(id="status")
        yield RichLog(markup=True)
        yield Footer()

    def on_mount(self) -> None:
        self.session = dbmod.open_session(self.db_path)
        self._show_current()

    def on_unmount(self) -> None:
        if self.session is not None:
            self.session.close()

    # UI helpers

    def _log(self, line: str) -> None:
        self.query_one(RichLog).write(line)

    def _set_status(self, text: str) -> None:
        self.query_one("#status", Static).update(Text.from_markup(text))

    @property
    def current(self) -> dbmod.Proposal | None:
        """The first pending proposal, queried fresh on every access."""
        if self.session is None:
            return None
        proposals = dbmod.pending(self.session)
        return proposals[0] if proposals else None

    def _show_current(self) -> None:
        panel = self.query_one("#proposal", Static)
        proposals = dbmod.pending(self.session) if self.session else []
        if not proposals:
            panel.update(Text("No pending proposals."))
            panel.border_title = "done"
            self._set_status(
                "Queue edits with `positions queue < payload.json`, "
                "press r to refresh or q to quit."
            )
            return
        proposal = proposals[0]
        panel.update(render_proposal(proposal))
        panel.border_title = f"#{proposal.id} — {len(proposals):,} pending"
        self._set_status("")

    # Actions

    def action_accept(self) -> None:
        if self.busy or self.session is None:
            return
        proposal = self.current
        if proposal is None:
            return
        self.busy = True
        self._set_status(f"Submitting #{proposal.id} {dbmod.display_name(proposal)}…")
        self.submit_worker(
            proposal.id,
            proposal.kind,
            proposal.entity,
            proposal.payload,
            proposal.comment,
        )

    def action_discard(self) -> None:
        if self.busy or self.session is None:
            return
        proposal = self.current
        if proposal is None:
            return
        dbmod.decide(self.session, proposal, dbmod.REJECTED)
        self._log(f"[red]✗[/] discarded #{proposal.id} {dbmod.display_name(proposal)}")
        self._show_current()

    def action_refresh(self) -> None:
        if not self.busy:
            self._show_current()

    def action_request_quit(self) -> None:
        if self.busy:
            self._set_status("Submitting — please wait.")
            return
        self.exit()

    # Background worker (HTTP only; reports back via messages)

    @work(thread=True)
    def submit_worker(
        self,
        proposal_id: int,
        kind: str,
        entity: str | None,
        payload: list[dict] | dict,
        comment: str,
    ) -> None:
        created: str | None = None
        try:
            with wikidata.auth_client() as client:
                if kind == proposals.CREATE:
                    assert isinstance(payload, dict)
                    created = wikidata.submit_create(client, payload, comment)
                else:
                    assert isinstance(entity, str) and isinstance(payload, list)
                    wikidata.submit_patch(client, entity, payload, comment)
        except wikidata.SubmitConflict as error:
            self.post_message(SubmitStale(proposal_id, str(error)))
        except wikidata.SubmitError as error:
            self.post_message(SubmitFailed(proposal_id, str(error)))
        else:
            self.post_message(Submitted(proposal_id, created))

    # Worker results

    def _reload(self, proposal_id: int) -> dbmod.Proposal:
        assert self.session is not None
        proposal = self.session.get(dbmod.Proposal, proposal_id)
        assert proposal is not None
        return proposal

    def on_submitted(self, message: Submitted) -> None:
        proposal = self._reload(message.proposal_id)
        dbmod.record_submission(self.session, proposal, message.created_entity)
        if message.created_entity is not None:
            self._log(f"[green]✓[/] created {message.created_entity} (#{proposal.id})")
        else:
            self._log(f"[green]✓[/] submitted #{proposal.id} {proposal.entity}")
        self.busy = False
        self._show_current()

    def on_submit_stale(self, message: SubmitStale) -> None:
        proposal = self._reload(message.proposal_id)
        dbmod.decide(self.session, proposal, dbmod.STALE, message.reason)
        self._log(
            f"[yellow]⚠[/] stale #{proposal.id} "
            f"{dbmod.display_name(proposal)}: {message.reason}"
        )
        self.busy = False
        self._show_current()

    def on_submit_failed(self, message: SubmitFailed) -> None:
        proposal = self._reload(message.proposal_id)
        self.busy = False
        self._log(
            f"[red]✗[/] #{proposal.id} {dbmod.display_name(proposal)} not submitted: "
            f"{message.reason}. Left pending."
        )
        self._set_status("Submission failed — decide again or quit.")


def review(db_path: Path) -> None:
    PositionsApp(db_path).run()
