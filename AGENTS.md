# AGENTS.md

`positions` is a personal CLI for reviewing improvements to political position
items on Wikidata. Its unit of work is an item used as a `position held (P39)`
value, not a politician.

`research.md` is the domain specification. Read the relevant section before
changing proposal or submission rules. The implemented workflow is currently
the deterministic P17/P1001 jurisdiction backfill described in §3.

## Commands

```bash
uv sync
uv run positions sync --limit 400    # build a small local model
uv run positions propose             # create pending P17/P1001 proposals
uv run positions                     # interactively accept/discard proposals
uv run positions show <qid>          # inspect a local entity
```

Accepting submits to Wikidata and requires `WIKIDATA_ACCESS_TOKEN`; see
`.env.example`. Use a separate `--db` file for smoke tests and do not accept an
edit during automated verification.

There is no test suite yet. After sync or proposal changes, smoke-test with:

```bash
uv run positions sync --limit 400 --db /tmp/positions-smoke.duckdb
uv run positions propose --db /tmp/positions-smoke.duckdb
```

## Project structure

```text
src/positions/
  cli.py         Typer commands and review-loop entry point
  sync.py        revision-aware universe and entity sync
  wdqs.py        paginated WDQS queries and retries
  wikidata.py    entity parsing, live checks, and authenticated edits
  db.py          DuckDB schema, transactions, and claim ingestion
  candidates.py  P17/P1001 proposal creation, selection, and decisions
  review.py      interactive accept/discard flow
research.md      audit findings and modeling rules
```

## Invariants

- A human must explicitly accept every edit. Never add unattended submission.
- Generate proposals from the local model only. Immediately before submission,
  re-fetch the live position and source body, validate all ranks, and use
  revision-based concurrency.
- Submit the paired P17/P1001 proposal atomically or not at all.
- Only propose the §3 backfill when the position is directly `P31 = Q294414`,
  has exactly one P361 body, has neither target property, and that body has
  exactly one non-deprecated P17 and P1001 value.
- Do not infer a country for generic roles such as president or senator.
- The `claim` table mirrors Wikidata only. Atomic P17/P1001 proposals and
  their human decisions live in the separate `proposal` and `decision` tables;
  decided proposals remain as tombstones so they are not proposed again.
- Keep the project local and serverless with minimal dependencies.
- Keep only the current schema and API shapes in the code. Do not add migrations,
  backward-compatibility branches, or legacy fallbacks: when the schema changes,
  delete the local DuckDB file and rebuild it with `positions sync`.

## Implementation notes

- WDQS can time out or truncate large results. Keep stable pagination and retry
  429/5xx responses.
- `wbgetentities` with `formatversion=2` returns `entities` as a QID-keyed map.
  Live submission checks must include deprecated statements even though
  the local sync omits them.
- Guard empty DuckDB `executemany` calls.
- Use Python 3.12+, type hints, and Ruff defaults.
