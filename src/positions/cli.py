"""positions CLI: sync, inspection, and the interactive review TUI."""

from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from . import db as dbmod
from . import sync as syncmod
from . import tui

app = typer.Typer(help="Personal tool for auditing political positions on Wikidata.")
console = Console()

DbOption = typer.Option(Path("positions.duckdb"), "--db", help="DuckDB file path.")

load_dotenv()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context, db: Path = DbOption):
    """Review proposals one at a time; accept pushes to Wikidata."""
    if ctx.invoked_subcommand is None:
        tui.review(db)


@app.command()
def sync(
    limit: int | None = typer.Option(None, help="Limit universe size (for testing)."),
    db: Path = DbOption,
):
    """Sync the local world model from WDQS + the Wikidata API."""
    syncmod.sync(db, limit=limit)


@app.command()
def show(qid: str, db: Path = DbOption):
    """Show the local record for an entity."""
    qid = qid.upper()
    con = dbmod.connect(db)
    try:
        row = con.execute(
            """
            SELECT e.qid, e.en_label, e.en_description, e.is_position, p.links
            FROM entity e
            LEFT JOIN position p ON p.qid = e.qid
            WHERE e.qid = ?
            """,
            [qid],
        ).fetchone()
        if row is None:
            console.print(f"[red]{qid} not in local model — run sync first.")
            raise typer.Exit(1)

        console.print(f"[bold]{row[0]}[/] {row[1] or ''}")
        if row[2]:
            console.print(f"  {row[2]}")
        if row[3]:
            console.print(f"  in P39 universe with {row[4]} truthy links")

        claims = con.execute(
            """
            SELECT c.property, c.value, c.rank, value_entity.en_label
            FROM claim c
            LEFT JOIN entity value_entity ON value_entity.qid = c.value
            WHERE c.subject = ?
            ORDER BY c.property, c.value
            """,
            [qid],
        ).fetchall()
    finally:
        con.close()

    table = Table("property", "value", "rank")
    for prop, value, rank, label in claims:
        table.add_row(prop, f"{value} {label or ''}", rank)
    console.print(table)


if __name__ == "__main__":
    app()
