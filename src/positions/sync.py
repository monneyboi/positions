"""Sync the local world model from Wikidata."""

from collections.abc import Iterable, Mapping
from itertools import batched
from pathlib import Path

import duckdb
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from . import db as dbmod
from . import wdqs, wikidata

# Claims whose item values we also fetch (one hop), so checks and review
# UIs can see bodies, jurisdictions, and parent classes with labels.
RELATED_HOPS = ("P31", "P279", "P17", "P1001", "P361", "P2389")

console = Console()


def _progress() -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("•"),
        TimeElapsedColumn(),
        TextColumn("•"),
        TimeRemainingColumn(),
        console=console,
    )


def _local_revisions(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    return {
        qid: lastrevid
        for qid, lastrevid in con.execute(
            "SELECT qid, lastrevid FROM entity"
        ).fetchall()
    }


def _remote_revisions(qids: Iterable[str], desc: str) -> dict[str, int]:
    unique_qids = list(dict.fromkeys(qids))
    if not unique_qids:
        return {}

    total_chunks = (
        len(unique_qids) + wdqs.REVISION_CHUNK_SIZE - 1
    ) // wdqs.REVISION_CHUNK_SIZE
    with _progress() as progress:
        task = progress.add_task(desc, total=total_chunks)

        def report_retry(message: str) -> None:
            progress.console.print(f"  [yellow]{message}[/]")

        def report_chunk(done: int, total: int) -> None:
            progress.update(task, completed=done, total=total)

        revisions = wdqs.remote_revisions(
            unique_qids, on_retry=report_retry, on_chunk=report_chunk
        )

    console.print(
        f"  Retrieved revisions for {len(revisions):,} of {len(unique_qids):,} QIDs"
    )
    return revisions


def _stale_qids(
    qids: Iterable[str],
    local_revisions: Mapping[str, int],
    remote_revisions: Mapping[str, int],
) -> list[str]:
    """QIDs missing locally or newer in WDQS than in the local model."""
    stale = []
    for qid in dict.fromkeys(qids):
        local_rev = local_revisions.get(qid)
        remote_rev = remote_revisions.get(qid)
        if local_rev is None or remote_rev is None or remote_rev > local_rev:
            stale.append(qid)
    return stale


def _store_entity_batch(
    con: duckdb.DuckDBPyConnection,
    parsed_entities: tuple[dict, ...],
    is_position: bool,
) -> None:
    """Store an API batch in one transaction instead of committing per entity."""
    con.execute("BEGIN TRANSACTION")
    try:
        for parsed in parsed_entities:
            dbmod.upsert_entity(con, parsed, is_position)
        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        raise


def _fetch_and_store(
    con: duckdb.DuckDBPyConnection,
    qids: list[str],
    is_position: bool,
    desc: str,
) -> int:
    if not qids:
        console.print(f"  [green]No {desc} to fetch; all are current.[/]")
        return 0

    stored = 0
    with _progress() as progress:
        task = progress.add_task(desc, total=len(qids))

        def report_retry(message: str) -> None:
            progress.console.print(f"  [yellow]{message}[/]")

        parsed_entities = wikidata.fetch_entities(qids, on_retry=report_retry)
        for parsed_batch in batched(parsed_entities, wikidata.BATCH_SIZE):
            _store_entity_batch(con, parsed_batch, is_position)
            stored += len(parsed_batch)
            progress.update(task, completed=stored)

        # Missing/deleted QIDs are still processed, though the API does not
        # yield an entity for them. Finish the request progress explicitly.
        progress.update(task, completed=len(qids))

    missing = len(qids) - stored
    result = f"  Stored {stored:,} {desc}"
    if missing:
        result += f"; {missing:,} QIDs were missing from the API"
    console.print(result)
    return stored


def _replace_position_universe(
    con: duckdb.DuckDBPyConnection, universe: dict[str, int]
) -> None:
    """Replace the universe atomically and without one commit per row."""
    con.execute("BEGIN TRANSACTION")
    try:
        con.execute("DELETE FROM position")
        con.execute("UPDATE entity SET is_position = FALSE")
        if universe:
            con.executemany(
                "INSERT INTO position (qid, links) VALUES (?, ?)",
                list(universe.items()),
            )
            con.execute(
                """
                UPDATE entity
                SET is_position = TRUE
                WHERE qid IN (SELECT qid FROM position)
                """
            )
        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        raise


def _related_qids(con: duckdb.DuckDBPyConnection) -> list[str]:
    """One-hop item values referenced by position entities."""
    properties = ",".join(f"'{prop}'" for prop in RELATED_HOPS)
    return [
        row[0]
        for row in con.execute(
            f"""
            SELECT DISTINCT c.value
            FROM claim c
            JOIN position p ON p.qid = c.subject
            WHERE c.property IN ({properties})
              AND c.value_type = 'item'
            ORDER BY c.value
            """
        ).fetchall()
    ]


def sync(db_path: Path, limit: int | None = None) -> None:
    con = dbmod.connect(db_path)

    # 1. Discover the position universe from WDQS.
    console.print("[bold]1/3 Discovering P39 position IDs and usage counts[/]")
    console.print(
        "  WDQS aggregates each page before returning it; a page may take a while."
    )
    universe: dict[str, int] = {}

    def report_wdqs(message: str) -> None:
        console.print(f"  [cyan]WDQS[/] {message}")

    for qid, links in wdqs.position_universe(max_items=limit, on_status=report_wdqs):
        universe[qid] = links

    console.print(f"  Saving {len(universe):,} positions to {db_path}...")
    _replace_position_universe(con, universe)
    console.print(f"  [green]Universe saved: {len(universe):,} positions[/]")

    # 2. Refresh only missing or modified position entities.
    remote_revisions = _remote_revisions(universe.keys(), "Checking position revisions")
    todo = _stale_qids(universe.keys(), _local_revisions(con), remote_revisions)
    current = len(universe) - len(todo)
    console.print(
        f"[bold]2/3 Refreshing {len(todo):,} position entities ({current:,} current)[/]"
    )
    _fetch_and_store(con, todo, is_position=True, desc="positions")

    # 3. Refresh one-hop related entities (bodies, jurisdictions, classes...).
    related = _related_qids(con)
    remote_revisions = _remote_revisions(related, "Checking related revisions")
    todo_related = _stale_qids(related, _local_revisions(con), remote_revisions)
    current_related = len(related) - len(todo_related)
    console.print(
        f"[bold]3/3 Refreshing {len(todo_related):,} related entities "
        f"({current_related:,} current)[/]"
    )
    _fetch_and_store(con, todo_related, is_position=False, desc="related")

    n_entities = con.execute("SELECT COUNT(*) FROM entity").fetchone()[0]
    n_claims = con.execute("SELECT COUNT(*) FROM claim").fetchone()[0]
    con.close()
    console.print(
        f"[bold green]Done.[/] {len(universe):,} positions, "
        f"{n_entities:,} entities, {n_claims:,} claims in {db_path}."
    )
