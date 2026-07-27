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
    """Review queued batches one at a time; accept pushes to Wikidata."""
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
        batches = proposals_mod.load(file.read())
    except proposals_mod.PayloadError as error:
        console.print(f"[red]invalid payload:[/] {error}")
        raise typer.Exit(1) from error

    with dbmod.open_session(db) as session:
        added, skipped = dbmod.enqueue(session, batches)

    for proposal in added:
        console.print(
            f"[green]+[/] #{proposal.id} {dbmod.display_name(proposal)} "
            f"(batch {proposal.batch})"
        )
    for edit, reason in skipped:
        target = (
            edit["params"].get("statement_id")
            or edit["params"].get("item_id")
            or "new item"
        )
        console.print(f"[yellow]~[/] {target} ({edit['operationId']}) — {reason}")
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
    table = Table("id", "batch", "operation", "entity", "status", "ops", "rationale")
    for p in rows:
        patch = p.body.get("patch") if p.body else None
        ops = str(len(patch)) if isinstance(patch, list) else "—"
        rationale = p.rationale if len(p.rationale) <= 60 else p.rationale[:59] + "…"
        table.add_row(
            str(p.id),
            p.batch,
            p.operation,
            dbmod.display_name(p),
            p.status,
            ops,
            rationale,
        )
    console.print(table)


@app.command()
def show(ctx: typer.Context, proposal_id: int):
    """Show one proposal in full: operation, params, body, batch rationale."""
    db: Path = ctx.obj
    with dbmod.open_session(db) as session:
        p = session.get(dbmod.Proposal, proposal_id)
    if p is None:
        console.print(f"[red]no proposal #{proposal_id}")
        raise typer.Exit(1)

    console.print(
        f"[bold]#{p.id} {dbmod.display_name(p)}[/] \\[{p.status}] {p.operation} "
        f"(batch {p.batch})"
    )
    payload: dict = {"params": p.params}
    if p.body is not None:
        payload["body"] = p.body
    console.print(JSON(json.dumps(payload)))
    console.print(f"  rationale: {p.rationale}")
    if p.note:
        console.print(f"  note:      {p.note}")


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
