"""positions CLI."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from . import checks as checksmod
from . import db as dbmod
from . import sync as syncmod

app = typer.Typer(help="Personal tool for auditing political positions on Wikidata.")
console = Console()

DbOption = typer.Option(Path("positions.duckdb"), "--db", help="DuckDB file path.")


@app.command()
def sync(
    limit: Optional[int] = typer.Option(None, help="Limit universe size (for testing)."),
    db: Path = DbOption,
):
    """Sync the local world model from WDQS + the Wikidata API."""
    syncmod.sync(db, limit=limit)


@app.command(name="check")
def check(
    name: Optional[str] = typer.Argument(None, help="Check to run (default: all)."),
    db: Path = DbOption,
):
    """Run audit checks and refresh review queues."""
    con = dbmod.connect(db)
    selected = (
        {name: checksmod.CHECKS[name]}
        if name
        else checksmod.CHECKS
    )
    if name and name not in checksmod.CHECKS:
        console.print(f"[red]Unknown check '{name}'. Available: {', '.join(checksmod.CHECKS)}")
        raise typer.Exit(1)

    table = Table("check", "queue size", "description")
    for cname, c in selected.items():
        n = checksmod.refresh_queue(con, c)
        table.add_row(cname, str(n), c.description)
    console.print(table)


@app.command()
def show(qid: str, db: Path = DbOption):
    """Show the local record for an entity."""
    con = dbmod.connect(db)
    row = con.execute(
        "SELECT qid, en_label, en_description, is_position FROM entity WHERE qid = ?",
        [qid.upper()],
    ).fetchone()
    if not row:
        console.print(f"[red]{qid} not in local model — run sync first.")
        raise typer.Exit(1)
    console.print(f"[bold]{row[0]}[/] {row[1] or ''}")
    if row[2]:
        console.print(f"  {row[2]}")
    if row[3]:
        links = con.execute("SELECT links FROM position WHERE qid = ?", [qid.upper()]).fetchone()
        console.print(f"  in P39 universe with {links[0]} truthy links")
    claims = con.execute(
        "SELECT property, value, rank FROM claim WHERE subject = ? ORDER BY property",
        [qid.upper()],
    ).fetchall()
    table = Table("property", "value", "rank")
    for prop, val, rank in claims:
        label = con.execute("SELECT en_label FROM entity WHERE qid = ?", [val]).fetchone()
        table.add_row(prop, f"{val} {label[0] if label and label[0] else ''}", rank)
    console.print(table)


@app.command()
def queue(
    name: str = typer.Argument(..., help="Check name."),
    limit: int = typer.Option(20, help="Max rows to show."),
    db: Path = DbOption,
):
    """Show the current review queue for a check."""
    con = dbmod.connect(db)
    rows = con.execute(
        """
        SELECT q.qid, q.details, d.decision
        FROM queue q
        LEFT JOIN decision d ON d.check_name = q.check_name AND d.qid = q.qid
        WHERE q.check_name = ?
        ORDER BY (q.details->>'links')::INTEGER DESC NULLS LAST
        LIMIT ?
        """,
        [name, limit],
    ).fetchall()
    table = Table("qid", "decision", "details")
    for qid, details, decision in rows:
        table.add_row(qid, decision or "[dim]pending", details)
    console.print(table)


if __name__ == "__main__":
    app()
