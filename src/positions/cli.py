"""positions CLI: queue proposed edits, inspect the queue, and review them."""

import json
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.json import JSON
from rich.table import Table

from . import db as dbmod
from . import proposals as proposals_mod
from . import tui

app = typer.Typer(
    help="Personal queue for human-reviewed Wikidata edits to political positions."
)
console = Console()

FileArgument = typer.Argument("-", help="JSON payload file, or stdin.")
DbOption = typer.Option(dbmod.DEFAULT_DB, "--db", help="SQLite file path.")

load_dotenv()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context, db: Path = DbOption):
    """Review queued proposals one at a time; accept pushes to Wikidata."""
    ctx.obj = db
    if ctx.invoked_subcommand is None:
        tui.review(db)


@app.command()
def queue(
    ctx: typer.Context,
    file: typer.FileText = FileArgument,
):
    """Enqueue proposed edits from a JSON payload (agent-facing)."""
    db: Path = ctx.obj
    try:
        payloads = proposals_mod.load(file.read())
    except proposals_mod.PayloadError as error:
        console.print(f"[red]invalid payload:[/] {error}")
        raise typer.Exit(1) from error

    with dbmod.open_session(db) as session:
        added, skipped = dbmod.enqueue(session, payloads)

    for proposal in added:
        console.print(
            f"[green]+[/] #{proposal.id} {proposal.entity}: {proposal.comment}"
        )
    for payload, reason in skipped:
        console.print(
            f"[yellow]~[/] {payload['entity']}: {payload['comment']} — {reason}"
        )
    console.print(f"queued {len(added)}, skipped {len(skipped)}")


@app.command(name="list")
def list_cmd(
    ctx: typer.Context,
    status: str = typer.Option(
        "pending", help="Filter by status: pending|submitted|rejected|stale|all."
    ),
):
    """List proposals in the queue."""
    db: Path = ctx.obj
    if status != "all" and status not in dbmod.STATUSES:
        console.print(f"[red]unknown status {status!r}")
        raise typer.Exit(1)
    with dbmod.open_session(db) as session:
        rows = dbmod.by_status(session, None if status == "all" else status)

    if not rows:
        console.print(f"no {status} proposals")
        return
    table = Table("id", "entity", "status", "ops", "comment")
    for p in rows:
        table.add_row(str(p.id), p.entity, p.status, str(len(p.patch)), p.comment)
    console.print(table)


@app.command()
def show(ctx: typer.Context, proposal_id: int):
    """Show one proposal in full, including rationale and sources."""
    db: Path = ctx.obj
    with dbmod.open_session(db) as session:
        p = session.get(dbmod.Proposal, proposal_id)
    if p is None:
        console.print(f"[red]no proposal #{proposal_id}")
        raise typer.Exit(1)

    console.print(f"[bold]#{p.id} {p.entity}[/] \\[{p.status}]")
    console.print(JSON(json.dumps(p.patch)))
    console.print(f"  comment:   {p.comment}")
    if p.rationale:
        console.print(f"  rationale: {p.rationale}")
    for source in p.sources:
        console.print(f"  source:    {source}")
    if p.note:
        console.print(f"  note:      {p.note}")
    if p.submission_revision_id:
        console.print(f"  submitted as revision {p.submission_revision_id:,}")


@app.command()
def drop(ctx: typer.Context, proposal_id: int):
    """Delete a PENDING proposal without leaving a tombstone."""
    db: Path = ctx.obj
    with dbmod.open_session(db) as session:
        p = session.get(dbmod.Proposal, proposal_id)
        if p is None:
            console.print(f"[red]no proposal #{proposal_id}")
            raise typer.Exit(1)
        if p.status != dbmod.PENDING:
            console.print(
                f"[red]#{proposal_id} is {p.status}; only pending proposals can be dropped"
            )
            raise typer.Exit(1)
        session.delete(p)
        session.commit()
    console.print(f"dropped #{proposal_id}")


if __name__ == "__main__":
    app()
