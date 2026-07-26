# AGENTS.md

`positions` is a personal human-in-the-loop queue for improving political
position items on Wikidata. An LLM agent researches and queues proposed
edits; a human reviews them in the TUI and only an explicit accept submits.

The local SQLite database holds **proposed edits only** — there is no
Wikidata mirror and no sync. The agent queries Wikidata itself — SPARQL
against the QLever mirror, live entity state via `wbgetentities` — plus
the web. Domain knowledge lives in pi skills under `.pi/skills/`, not in
code.

## Commands

```bash
uv sync
uv run positions queue proposals.json   # enqueue proposed edits (agent-facing)
uv run positions list --status all      # pending queue and tombstones
uv run positions show <id>              # full proposal detail
uv run positions                        # TUI: accept/discard queued proposals
```

Accepting submits to Wikidata and requires `WIKIDATA_ACCESS_TOKEN`; see
`.env.example`. Use a separate `--db` file for smoke tests and do not accept
an edit during automated verification.

There is no test suite yet. After queue or review changes, smoke-test with:

```bash
echo '{"proposals": []}' | uv run positions queue --db /tmp/smoke.sqlite
uv run positions list --db /tmp/smoke.sqlite
```

## Project structure

```text
src/positions/
  cli.py         Typer commands (queue/list/show/drop) and TUI entry point
  tui.py         Textual review loop over pending proposals
  proposals.py   queue JSON payload schema and validation
  wikidata.py    live duplicate checks and authenticated atomic edits
  db.py          SQLAlchemy/SQLite proposal queue and tombstones
.pi/skills/
  propose-edits/             agent workflow: research, verify, queue
  wikidata-querying/         QLever SPARQL mirror and live API reference
  wikidata-political-model/  political data modeling reference
  wikidata-labels/           labels, aliases, mul, and fallback reference
```

## Invariants

- A human must explicitly accept every edit. Never add unattended submission;
  the agent's only write path is `positions queue`.
- Proposals are add-only, item-valued statements; one proposal edits one
  entity and is submitted atomically or not at all.
- Immediately before submission, re-fetch the live entity, confirm the
  proposed statements are still new at every rank, and use baserevid
  concurrency. If live state changed, mark the proposal stale — never force
  an edit through.
- Terminal proposal states (submitted/rejected/stale) stay in the table as
  tombstones keyed by content fingerprint, so a decided edit is never
  proposed again.
- Keep the project local and serverless with minimal dependencies.
- Keep only the current schema and API shapes in the code. Do not add
  migrations, backward-compatibility branches, or legacy fallbacks: when the
  schema changes, delete the local SQLite file and requeue.

## Implementation notes

- `wbgetentities` with `formatversion=2` returns `entities` as a QID-keyed map.
  Live submission checks must include deprecated statements.
- Use Python 3.12+, type hints, and Ruff defaults.
