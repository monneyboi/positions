"""Textual TUI for reviewing queued batches of proposed edits.

Batches come from the queue (`positions queue`); the TUI never generates
them. The review unit is the batch: one rationale over one or more
edits, decided together. Live Wikidata is only touched on accept: each
edit is submitted in turn, verbatim, as one Wikibase REST API call — the
operationId the edit names, with its params and body. Edits address
stable identities (item ids, statement GUIDs, language codes), so if
live state drifted (404/409/412) the edit goes stale instead of editing
the wrong thing; any other failure is shown in the log and that edit
stays pending for another decision. Terminal states stay in the proposal
table as tombstones; the app itself only touches the database on the
main thread.
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
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widgets import Footer, Header, RichLog, Static

from . import db as dbmod
from . import wikidata


class Submitted(Message):
    """The edit was accepted by Wikidata."""

    def __init__(self, proposal_id: int, created_entity: str | None) -> None:
        super().__init__()
        self.proposal_id = proposal_id
        self.created_entity = created_entity  # a create's new entity id


class SubmitStale(Message):
    """An accept found changed live state; the edit went stale."""

    def __init__(self, proposal_id: int, reason: str) -> None:
        super().__init__()
        self.proposal_id = proposal_id
        self.reason = reason


class SubmitFailed(Message):
    """The edit failed; it stays pending so the human can retry."""

    def __init__(self, proposal_id: int, reason: str) -> None:
        super().__init__()
        self.proposal_id = proposal_id
        self.reason = reason


class BatchFinished(Message):
    """All edits of the accepted batch have a reported outcome."""


def render_edit(p: dbmod.Proposal) -> Group:
    """One edit exactly as it will be sent: header plus params and body."""
    payload: dict = {"params": p.params}
    if p.body is not None:
        payload["body"] = p.body
    return Group(
        Text.from_markup(f"[bold]#{p.id} {p.operation} {dbmod.display_name(p)}[/]"),
        JSON(json.dumps(payload)),
    )


def render_batch(rows: list[dbmod.Proposal]) -> Group:
    """The batch under review: the shared rationale, then every edit."""
    return Group(
        Text.from_markup(f"[bold]rationale:[/] {rows[0].rationale}"),
        *(render_edit(p) for p in rows),
    )


class PositionsApp(App):
    """Review loop over the live pending-batch queue."""

    TITLE = "positions"
    CSS = """
    #proposal {
        height: auto;
        max-height: 60%;
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
        Binding("a", "accept", "Accept batch"),
        Binding("d", "discard", "Discard batch"),
        Binding("r", "refresh", "Refresh"),
        Binding("q", "request_quit", "Quit"),
    ]

    def __init__(self, db_path: Path) -> None:
        super().__init__()
        self.db_path = db_path
        self.session: dbmod.Session | None = None
        self.busy = False  # a batch submission is in flight
        self.had_failure = False  # an edit in the in-flight batch failed

    def compose(self) -> ComposeResult:
        yield Header()
        yield VerticalScroll(Static(id="content"), id="proposal")
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
    def current_batch(self) -> tuple[str, list[dbmod.Proposal]] | None:
        """The first pending batch, queried fresh on every access."""
        if self.session is None:
            return None
        batches = dbmod.pending_batches(self.session)
        return batches[0] if batches else None

    def _show_current(self) -> None:
        panel = self.query_one("#proposal", VerticalScroll)
        content = self.query_one("#content", Static)
        batches = dbmod.pending_batches(self.session) if self.session else []
        if not batches:
            content.update(Text("No pending proposals."))
            panel.border_title = "done"
            self._set_status(
                "Queue edits with `positions queue < payload.json`, "
                "press r to refresh or q to quit."
            )
            return
        key, rows = batches[0]
        content.update(render_batch(rows))
        panel.scroll_home(animate=False)
        edits = f"{len(rows)} edit" + ("s" if len(rows) != 1 else "")
        pending = f"{len(batches):,} batch" + ("es" if len(batches) != 1 else "")
        panel.border_title = f"batch {key} — {edits} — {pending} pending"
        self._set_status("")

    # Actions

    def action_accept(self) -> None:
        if self.busy or self.session is None:
            return
        current = self.current_batch
        if current is None:
            return
        key, rows = current
        self.busy = True
        self.had_failure = False
        self._set_status(f"Submitting batch {key} ({len(rows)} edits)…")
        edits = [
            (p.id, {"operationId": p.operation, "params": p.params, "body": p.body})
            for p in rows
        ]
        self.submit_worker(key, edits)

    def action_discard(self) -> None:
        if self.busy or self.session is None:
            return
        current = self.current_batch
        if current is None:
            return
        key, rows = current
        for proposal in rows:
            dbmod.decide(self.session, proposal, dbmod.REJECTED)
        self._log(f"[red]✗[/] discarded batch {key} ({len(rows)} edits)")
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
        batch_key: str,
        edits: list[tuple[int, dict]],
    ) -> None:
        """Submit each edit of the batch in turn, reporting per-edit outcomes."""
        try:
            client = wikidata.auth_client()
        except wikidata.SubmitError as error:
            self.post_message(SubmitFailed(edits[0][0], str(error)))
            self.post_message(BatchFinished())
            return
        with client:
            for proposal_id, edit in edits:
                created: str | None = None
                try:
                    created = wikidata.submit(client, edit)
                except wikidata.SubmitConflict as error:
                    self.post_message(SubmitStale(proposal_id, str(error)))
                except wikidata.SubmitError as error:
                    self.post_message(SubmitFailed(proposal_id, str(error)))
                else:
                    self.post_message(Submitted(proposal_id, created))
        self.post_message(BatchFinished())

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

    def on_submit_stale(self, message: SubmitStale) -> None:
        proposal = self._reload(message.proposal_id)
        dbmod.decide(self.session, proposal, dbmod.STALE, message.reason)
        self._log(
            f"[yellow]⚠[/] stale #{proposal.id} "
            f"{dbmod.display_name(proposal)}: {message.reason}"
        )

    def on_submit_failed(self, message: SubmitFailed) -> None:
        proposal = self._reload(message.proposal_id)
        self.had_failure = True
        self._log(
            f"[red]✗[/] #{proposal.id} {dbmod.display_name(proposal)} not submitted: "
            f"{message.reason}. Left pending."
        )

    def on_batch_finished(self, message: BatchFinished) -> None:
        self.busy = False
        self._show_current()
        if self.had_failure:
            self._set_status("Some edits failed — decide again or quit.")


def review(db_path: Path) -> None:
    PositionsApp(db_path).run()
