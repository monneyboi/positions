"""positions CLI: queue proposed edits, inspect the queue, and review them."""

import sys
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from . import db as dbmod
from . import proposals as proposals_mod
from . import tui

app = typer.Typer(
    help="Personal queue for human-reviewed Wikidata edits to political positions."
)
console = Console()

FileArgument = typer.Argument("-", help="JSON payload file, or stdin.")
DbOption = typer.Option(Path("positions.sqlite"), "--db", help="SQLite file path.")

load_dotenv()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context, db: Path = DbOption):
    """Review queued proposals one at a time; accept pushes to Wikidata."""
    if ctx.invoked_subcommand is None:
        tui.review(db)


@app.command()
def queue(
    file: typer.FileText = FileArgument,
    db: Path = DbOption,
):
    """Enqueue proposed edits from a JSON payload (agent-facing)."""
    text = sys.stdin.read() if file is sys.stdin else file.read()
    try:
        payloads = proposals_mod.load(text)
    except proposals_mod.PayloadError as error:
        console.print(f"[red]invalid payload:[/] {error}")
        raise typer.Exit(1) from error

    with dbmod.open_session(db) as session:
        added, skipped = dbmod.enqueue(session, payloads)

    for proposal in added:
        console.print(
            f"[green]+[/] #{proposal.id} {proposal.entity}: {proposal.summary}"
        )
    for payload, reason in skipped:
        console.print(
            f"[yellow]~[/] {payload['entity']}: {payload['summary']} — {reason}"
        )
    console.print(f"queued {len(added)}, skipped {len(skipped)}")


@app.command(name="list")
def list_cmd(
    status: str = typer.Option(
        "pending", help="Filter by status: pending|submitted|rejected|stale|all."
    ),
    db: Path = DbOption,
):
    """List proposals in the queue."""
    from sqlalchemy import select

    with dbmod.open_session(db) as session:
        query = select(dbmod.Proposal).order_by(dbmod.Proposal.id)
        if status != "all":
            if status not in dbmod.STATUSES:
                console.print(f"[red]unknown status {status!r}")
                raise typer.Exit(1)
            query = query.where(dbmod.Proposal.status == status)
        rows = list(session.scalars(query))

    if not rows:
        console.print(f"no {status} proposals")
        return
    table = Table("id", "entity", "status", "statements", "summary")
    for p in rows:
        statements = ", ".join(f"{s['property']}→{s['value']}" for s in p.statements)
        table.add_row(str(p.id), p.entity, p.status, statements, p.summary)
    console.print(table)


@app.command()
def show(proposal_id: int, db: Path = DbOption):
    """Show one proposal in full, including rationale and sources."""
    with dbmod.open_session(db) as session:
        p = session.get(dbmod.Proposal, proposal_id)
    if p is None:
        console.print(f"[red]no proposal #{proposal_id}")
        raise typer.Exit(1)

    console.print(f"[bold]#{p.id} {p.entity}[/] \\[{p.status}]")
    for s in p.statements:
        console.print(f"  + {s['property']} → {s['value']}")
    console.print(f"  summary:   {p.summary}")
    if p.rationale:
        console.print(f"  rationale: {p.rationale}")
    for source in p.sources:
        console.print(f"  source:    {source}")
    if p.note:
        console.print(f"  note:      {p.note}")
    if p.submission_revision_id:
        console.print(f"  submitted as revision {p.submission_revision_id:,}")


@app.command()
def drop(proposal_id: int, db: Path = DbOption):
    """Delete a PENDING proposal without leaving a tombstone."""
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
