"""Interactive review and submission of jurisdiction proposals.

Accept and discard are persisted in the decision table. An accepted proposal
is re-fetched and validated against live Wikidata before its paired P17/P1001
claims are submitted atomically with revision-based concurrency.
"""

from pathlib import Path

import duckdb
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from . import candidates, wikidata
from . import db as dbmod

console = Console()

EDIT_SUMMARY = (
    "add P17/P1001 inherited from P361 body "
    "([[Wikidata:WikiProject every politician/Political data model]])"
)


class SubmitConflict(Exception):
    """Live Wikidata state disagrees with the local proposal."""


def _render(qid: str, d: dict, remaining: int) -> None:
    console.print(
        Panel(
            f"[bold]{d['label'] or '(no English label)'}[/] ({qid})"
            f" — {d['links']:,} P39 links\n\n"
            f"part of:  {d['body']['label'] or ''} ({d['body']['qid']})\n"
            f"[green]+ P17   country[/] → "
            f"{d['country']['label'] or ''} ({d['country']['qid']})\n"
            f"[green]+ P1001 applies to jurisdiction[/] → "
            f"{d['jurisdiction']['label'] or ''} ({d['jurisdiction']['qid']})",
            title=f"{remaining} proposal(s) left",
        )
    )


def _verify_live(client, qid: str, d: dict) -> int:
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
            f"{qid} now has P361 values {bodies or '(none)'}; "
            f"expected only {body_qid}"
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


def _record_edit(con: duckdb.DuckDBPyConnection, qid: str, entity: dict) -> None:
    """Apply the API response through the same claim-ingestion path as sync."""
    with dbmod.transaction(con):
        dbmod.update_entity_claims(
            con,
            qid,
            entity["lastrevid"],
            wikidata.parse_claims(entity),
        )
        candidates.record_submission(con, qid, entity["lastrevid"])


def _accept(con: duckdb.DuckDBPyConnection, qid: str, d: dict) -> bool:
    """Submit an accepted proposal; return whether review can continue."""
    try:
        with wikidata._auth_client() as client:
            try:
                baserevid = _verify_live(client, qid, d)
            except SubmitConflict as error:
                candidates.decide(con, qid, "skipped", str(error))
                console.print(f"  [yellow]Skipped: {error}.[/]")
                return True

            # Persist explicit human approval before entering the edit path.
            candidates.decide(con, qid, "approved")
            entity = wikidata.add_item_claims(
                client,
                qid,
                {"P17": d["country"]["qid"], "P1001": d["jurisdiction"]["qid"]},
                baserevid=baserevid,
                summary=EDIT_SUMMARY,
            )
    except wikidata.SubmitError as error:
        candidates.withdraw_approval(con, qid)
        console.print(f"  [red]Not submitted: {error}. Approval left pending.[/]")
        return False

    _record_edit(con, qid, entity)
    console.print(
        f"  [green]Submitted[/] — {qid} now at revision {entity['lastrevid']}"
    )
    return True


def _discard(con: duckdb.DuckDBPyConnection, qid: str) -> None:
    candidates.decide(con, qid, "rejected")


def review(db_path: Path) -> None:
    con = dbmod.connect(db_path)
    try:
        if candidates.count_pending(con) == 0:
            console.print(
                "[yellow]No pending proposals.[/] "
                "Run `positions propose` (after `positions sync`)."
            )
            return

        while (current := candidates.next_pending(con)) is not None:
            qid, details = current
            _render(qid, details, candidates.count_pending(con))
            action = Prompt.ask(
                "[bold]\\[a][/]ccept  [bold]\\[d][/]iscard  [bold]\\[q][/]uit",
                choices=["a", "d", "q"],
            )
            if action == "q":
                break
            if action == "d":
                _discard(con, qid)
            elif action == "a" and not _accept(con, qid, details):
                break

        console.print(
            f"[bold]Done.[/] {candidates.count_pending(con)} proposal(s) remain."
        )
    finally:
        con.close()
