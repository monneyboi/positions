"""Sync the local world model from Wikidata."""

from pathlib import Path

import duckdb
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn

from . import db as dbmod
from . import wdqs, wikidata

# Claims whose item values we also fetch (one hop), so checks and review
# UIs can see bodies, jurisdictions, and parent classes with labels.
RELATED_HOPS = ("P31", "P279", "P17", "P1001", "P361", "P2389")


def _known_qids(con: duckdb.DuckDBPyConnection) -> set[str]:
    return {r[0] for r in con.execute("SELECT qid FROM entity").fetchall()}


def _fetch_and_store(
    con: duckdb.DuckDBPyConnection, qids: list[str], is_position: bool, desc: str
) -> None:
    stored = 0
    with Progress(
        SpinnerColumn(),
        TextColumn(f"[bold]{desc}"),
        BarColumn(),
        MofNCompleteColumn(),
    ) as progress:
        task = progress.add_task(desc, total=len(qids))
        for parsed in wikidata.fetch_entities(qids):
            dbmod.upsert_entity(con, parsed, is_position)
            stored += 1
            progress.update(task, completed=stored)


def sync(db_path: Path, limit: int | None = None) -> None:
    con = dbmod.connect(db_path)

    # 1. Position universe from WDQS.
    print("Fetching position universe from WDQS (paginated, ~15 s/page)...")
    universe: dict[str, int] = {}
    for qid, links in wdqs.position_universe(max_items=limit):
        universe[qid] = links
    con.execute("DELETE FROM position")
    con.executemany(
        "INSERT INTO position (qid, links) VALUES (?, ?)",
        list(universe.items()),
    )
    print(f"Universe: {len(universe)} positions")

    # 2. Fetch position entities (skip ones already synced).
    known = _known_qids(con)
    todo = [q for q in universe if q not in known]
    print(f"Fetching {len(todo)} position entities ({len(known)} cached)...")
    _fetch_and_store(con, todo, is_position=True, desc="positions")

    # 3. One-hop related entities (bodies, jurisdictions, parent classes...).
    related = {
        row[0]
        for row in con.execute(
            f"""
            SELECT DISTINCT value FROM claim
            WHERE property IN ({",".join(f"'{p}'" for p in RELATED_HOPS)})
              AND value_type = 'item'
            """
        ).fetchall()
    }
    known = _known_qids(con)
    todo_related = sorted(related - known)
    print(f"Fetching {len(todo_related)} related entities...")
    _fetch_and_store(con, todo_related, is_position=False, desc="related")

    n_claims = con.execute("SELECT COUNT(*) FROM claim").fetchone()[0]
    print(f"Done. {len(known) + len(todo_related)} entities, {n_claims} claims.")
