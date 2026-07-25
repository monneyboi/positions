"""Textual TUI for reviewing jurisdiction proposals created on the fly.

Proposals are derived from the local model when needed and never stored.
While the human decides on the current proposal, a background worker already
selects the next candidate, so advancing is instant. Live Wikidata is only
touched on accept: the position and its body are re-fetched and validated,
then the paired P17/P1001 claims are submitted atomically with baserevid
concurrency. Human decisions are persisted as tombstones in the decision
table; the app itself only touches the database on the main thread.
"""

from pathlib import Path
from typing import ClassVar

import duckdb
import httpx
from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.widgets import Footer, Header, RichLog, Static

from . import candidates, wikidata
from . import db as dbmod

_FETCHING = object()  # sentinel: a prefetch worker is still running


class SubmitConflict(Exception):
    """Live Wikidata state disagrees with the local proposal."""


class Prefetched(Message):
    """Background worker selected the next candidate (None = queue empty)."""

    def __init__(self, candidate: tuple[str, dict] | None) -> None:
        super().__init__()
        self.candidate = candidate


class Submitted(Message):
    """The paired edit was accepted by Wikidata."""

    def __init__(self, qid: str, entity: dict) -> None:
        super().__init__()
        self.qid = qid
        self.entity = entity


class SubmitSkipped(Message):
    """An accept found changed live state; the candidate was skipped."""

    def __init__(self, qid: str, reason: str) -> None:
        super().__init__()
        self.qid = qid
        self.reason = reason


class SubmitFailed(Message):
    """The edit failed; the approval is withdrawn so the human can retry."""

    def __init__(self, qid: str, reason: str) -> None:
        super().__init__()
        self.qid = qid
        self.reason = reason


def verify_live(client: httpx.Client, qid: str, d: dict) -> int:
    """Validate the live preconditions and return the edit base revision."""
    live = wikidata.fetch_live(client, qid)
    live_claims = live.get("claims", {})
    blocking = [prop for prop in ("P17", "P1001") if live_claims.get(prop)]
    if blocking:
        raise SubmitConflict(
            f"{qid} now has live {', '.join(blocking)} statement(s) "
            "(any rank) — someone got there first"
        )
    if "Q294414" not in wikidata.non_deprecated_values(live, "P31"):
        raise SubmitConflict(f"{qid} is no longer directly typed as a public office")

    body_qid = d["body"]["qid"]
    bodies = wikidata.non_deprecated_values(live, "P361")
    if bodies != [body_qid]:
        raise SubmitConflict(
            f"{qid} now has P361 values {bodies or '(none)'}; expected only {body_qid}"
        )

    body = wikidata.fetch_live(client, body_qid)
    for prop, expected in (
        ("P17", d["country"]["qid"]),
        ("P1001", d["jurisdiction"]["qid"]),
    ):
        values = wikidata.non_deprecated_values(body, prop)
        if values != [expected]:
            raise SubmitConflict(
                f"body {body_qid} now has {prop} values {values or '(none)'}; "
                f"expected only {expected}"
            )
    return live["lastrevid"]


def render_proposal(qid: str, d: dict) -> Text:
    return Text.from_markup(
        f"[bold]{d['label'] or '(no English label)'}[/] ({qid})"
        f" — {d['links']:,} P39 links\n\n"
        f"part of:  {d['body']['label'] or ''} ({d['body']['qid']})\n"
        f"[green]+ P17   country[/] → "
        f"{d['country']['label'] or ''} ({d['country']['qid']})\n"
        f"[green]+ P1001 applies to jurisdiction[/] → "
        f"{d['jurisdiction']['label'] or ''} ({d['jurisdiction']['qid']})"
    )


class PositionsApp(App):
    """Review loop: on-the-fly proposals, prefetched in the background."""

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
        Binding("q", "request_quit", "Quit"),
    ]

    def __init__(self, db_path: Path) -> None:
        super().__init__()
        self.db_path = db_path
        self.con: duckdb.DuckDBPyConnection | None = None
        self.current: tuple[str, dict] | None = None
        self.upcoming: tuple[str, dict] | None | object = _FETCHING
        self.busy = False  # a submission is in flight

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(id="proposal")
        yield Static(id="status")
        yield RichLog(markup=True)
        yield Footer()

    def on_mount(self) -> None:
        self.con = dbmod.connect(self.db_path)
        self._set_proposal(Text("Loading…"))
        self.prefetch_worker(exclude=None)

    def on_unmount(self) -> None:
        if self.con is not None:
            self.con.close()

    # UI helpers

    def _log(self, line: str) -> None:
        self.query_one(RichLog).write(line)

    def _set_status(self, text: str) -> None:
        self.query_one("#status", Static).update(Text.from_markup(text))

    def _set_proposal(self, text: Text, title: str = "") -> None:
        panel = self.query_one("#proposal", Static)
        panel.update(text)
        panel.border_title = title

    # Review flow (main thread only touches the database)

    def _show(self, candidate: tuple[str, dict]) -> None:
        """Display a candidate and prefetch the one after it."""
        assert self.con is not None
        qid, details = candidate
        self.current = candidate
        self.upcoming = _FETCHING
        remaining = candidates.count_candidates(self.con)
        self._set_proposal(
            render_proposal(qid, details), f"{remaining:,} candidate(s) left"
        )
        self._set_status("")
        self.prefetch_worker(exclude=qid)

    def _advance(self) -> None:
        """Move to the prefetched next candidate."""
        if self.upcoming is _FETCHING:
            # Rare: the human decided faster than the local query. The
            # in-flight prefetch will pick up the current slot on arrival.
            self.current = None
            self._set_proposal(Text("Loading…"))
        elif self.upcoming is None:
            self.current = None
            self._set_proposal(Text("No pending candidates."), "done")
            self._set_status(
                "Run `positions sync` to refresh the local model, "
                "then restart the review. Press q to quit."
            )
        else:
            self._show(self.upcoming)

    def action_accept(self) -> None:
        if self.busy or self.current is None:
            return
        assert self.con is not None
        qid, details = self.current
        self.busy = True
        # Persist explicit human approval before entering the edit path.
        candidates.decide(self.con, qid, "approved")
        self._set_status(f"Submitting {qid}…")
        self.submit_worker(qid, details)

    def action_discard(self) -> None:
        if self.busy or self.current is None:
            return
        assert self.con is not None
        qid, _ = self.current
        candidates.decide(self.con, qid, "rejected")
        self._log(f"[red]✗[/] discarded {qid}")
        self._advance()

    def action_request_quit(self) -> None:
        if self.busy:
            self._set_status("Submitting — please wait.")
            return
        self.exit()

    # Background workers (report back via messages)

    @work(thread=True)
    def prefetch_worker(self, exclude: str | None) -> None:
        con = dbmod.connect(self.db_path)
        try:
            candidate = candidates.next_candidate(con, exclude=exclude)
        finally:
            con.close()
        self.post_message(Prefetched(candidate))

    @work(thread=True)
    def submit_worker(self, qid: str, details: dict) -> None:
        try:
            with wikidata._auth_client() as client:
                baserevid = verify_live(client, qid, details)
                entity = wikidata.add_item_claims(
                    client,
                    qid,
                    {
                        "P17": details["country"]["qid"],
                        "P1001": details["jurisdiction"]["qid"],
                    },
                    baserevid=baserevid,
                )
        except SubmitConflict as error:
            self.post_message(SubmitSkipped(qid, str(error)))
        except wikidata.SubmitError as error:
            self.post_message(SubmitFailed(qid, str(error)))
        else:
            self.post_message(Submitted(qid, entity))

    # Worker results

    def on_prefetched(self, message: Prefetched) -> None:
        if self.current is None:
            # We were waiting on this prefetch (startup or fast decider).
            if message.candidate is not None:
                self._show(message.candidate)
            else:
                self.upcoming = None
                self._advance()
        else:
            self.upcoming = message.candidate

    def on_submitted(self, message: Submitted) -> None:
        assert self.con is not None
        qid, entity = message.qid, message.entity
        # Apply the API response through the same claim-ingestion path as sync.
        with dbmod.transaction(self.con):
            dbmod.update_entity_claims(
                self.con,
                qid,
                entity["lastrevid"],
                wikidata.parse_claims(entity),
            )
            candidates.record_submission(self.con, qid, entity["lastrevid"])
        self._log(f"[green]✓[/] submitted {qid} — revision {entity['lastrevid']:,}")
        self.busy = False
        self._advance()

    def on_submit_skipped(self, message: SubmitSkipped) -> None:
        assert self.con is not None
        candidates.decide(self.con, message.qid, "skipped", message.reason)
        self._log(f"[yellow]⚠[/] skipped {message.qid}: {message.reason}")
        self.busy = False
        self._advance()

    def on_submit_failed(self, message: SubmitFailed) -> None:
        assert self.con is not None
        candidates.withdraw_approval(self.con, message.qid)
        self.busy = False
        self._log(
            f"[red]✗[/] {message.qid} not submitted: {message.reason}. "
            "Approval left pending."
        )
        self._set_status("Submission failed — decide again or quit.")


def review(db_path: Path) -> None:
    PositionsApp(db_path).run()
