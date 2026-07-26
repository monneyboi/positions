"""Textual TUI for reviewing queued proposals.

Proposals come from the queue (`positions queue`); the TUI never generates
them. Live Wikidata is only touched on accept: the entity is re-fetched, the
proposed statements are checked against every live rank, and the edit is
submitted atomically with baserevid concurrency. Terminal states stay in the
proposal table as tombstones; the app itself only touches the database on
the main thread.
"""

from pathlib import Path
from typing import ClassVar

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.widgets import Footer, Header, RichLog, Static

from . import db as dbmod
from . import wikidata


class Submitted(Message):
    """The edit was accepted by Wikidata."""

    def __init__(self, proposal_id: int, revision_id: int) -> None:
        super().__init__()
        self.proposal_id = proposal_id
        self.revision_id = revision_id


class SubmitSkipped(Message):
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


def render_proposal(p: dbmod.Proposal) -> Text:
    statements = "\n".join(
        f"[green]+ {s['property']}[/] → {s['value']}" for s in p.statements
    )
    lines = [f"[bold]{p.entity}[/] — {p.summary}", "", statements]
    if p.rationale:
        lines += ["", f"rationale: {p.rationale}"]
    for source in p.sources:
        lines.append(f"source: {source}")
    return Text.from_markup("\n".join(lines))


class PositionsApp(App):
    """Review loop over the pending proposals queued at startup."""

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
        proposal = self.current
        if proposal is None:
            panel.update(Text("No pending proposals."))
            panel.border_title = "done"
            self._set_status(
                "Queue edits with `positions queue < payload.json`, "
                "press r to refresh or q to quit."
            )
            return
        assert self.session is not None
        panel.update(render_proposal(proposal))
        count = len(dbmod.pending(self.session))
        panel.border_title = f"#{proposal.id} — {count:,} pending"
        self._set_status("")

    def _advance(self) -> None:
        self._show_current()

    # Actions

    def action_accept(self) -> None:
        if self.busy or self.session is None:
            return
        proposal = self.current
        if proposal is None:
            return
        self.busy = True
        self._set_status(f"Submitting #{proposal.id} {proposal.entity}…")
        self.submit_worker(
            proposal.id, proposal.entity, proposal.statements, proposal.summary
        )

    def action_discard(self) -> None:
        if self.busy or self.session is None:
            return
        proposal = self.current
        if proposal is None:
            return
        dbmod.decide(self.session, proposal, dbmod.REJECTED)
        self._log(f"[red]✗[/] discarded #{proposal.id} {proposal.entity}")
        self._advance()

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
        self, proposal_id: int, entity: str, statements: list[dict], summary: str
    ) -> None:
        try:
            with wikidata._auth_client() as client:
                baserevid = wikidata.verify_live(client, entity, statements)
                response = wikidata.add_item_claims(
                    client, entity, statements, baserevid=baserevid, summary=summary
                )
        except wikidata.SubmitConflict as error:
            self.post_message(SubmitSkipped(proposal_id, str(error)))
        except wikidata.SubmitError as error:
            self.post_message(SubmitFailed(proposal_id, str(error)))
        else:
            self.post_message(Submitted(proposal_id, response["lastrevid"]))

    # Worker results

    def _reload(self, proposal_id: int) -> dbmod.Proposal:
        assert self.session is not None
        proposal = self.session.get(dbmod.Proposal, proposal_id)
        assert proposal is not None
        return proposal

    def on_submitted(self, message: Submitted) -> None:
        proposal = self._reload(message.proposal_id)
        dbmod.record_submission(self.session, proposal, message.revision_id)
        self._log(
            f"[green]✓[/] submitted #{proposal.id} {proposal.entity}"
            f" — revision {message.revision_id:,}"
        )
        self.busy = False
        self._advance()

    def on_submit_skipped(self, message: SubmitSkipped) -> None:
        proposal = self._reload(message.proposal_id)
        dbmod.decide(self.session, proposal, dbmod.STALE, message.reason)
        self._log(
            f"[yellow]⚠[/] stale #{proposal.id} {proposal.entity}: {message.reason}"
        )
        self.busy = False
        self._advance()

    def on_submit_failed(self, message: SubmitFailed) -> None:
        proposal = self._reload(message.proposal_id)
        self.busy = False
        self._log(
            f"[red]✗[/] #{proposal.id} {proposal.entity} not submitted: "
            f"{message.reason}. Left pending."
        )
        self._set_status("Submission failed — decide again or quit.")


def review(db_path: Path) -> None:
    PositionsApp(db_path).run()
