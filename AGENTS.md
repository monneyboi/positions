# AGENTS.md

Personal tool for auditing and improving political positions on Wikidata,
across all countries. The unit of work is the **position** (P39 value), not
the politician — this is the low-level, single-user counterpart to PoliLoom
(~/projects/poliloom), which is a community web app centered on politicians.

`research.md` is the domain spec: it contains the Wikidata audit this tool
operationalizes, the modeling rules, and the safeguards. Read the relevant
section before touching checks or submission logic.

## Setup commands

```bash
uv sync                          # install deps
uv run positions sync --limit 400   # small test slice into positions.duckdb
uv run positions check           # run all audit checks, refresh queues
uv run positions queue <check>   # inspect a queue
uv run positions show <qid>      # inspect a local entity
```

There is no test suite yet; checks are verified with inline scripts against
an in-memory DuckDB (see git history for examples). Run a `--limit 400`
sync + `check` as the smoke test after changing sync/check code.

## Project structure

```
src/positions/
  cli.py       # typer CLI: sync, check, show, queue
  sync.py      # orchestrates universe fetch + entity fetch
  wdqs.py      # WDQS client: paginated position-universe query, retries
  wikidata.py  # wbgetentities batches, claim parsing (KEEP_CLAIMS allowlist)
  db.py        # DuckDB schema + upsert (position, entity, claim, queue, decision)
  checks.py    # named audit checks (pure SQL over local model) -> queue table
research.md    # the audit/spec — authoritative for check semantics
```

## Domain rules — read before editing check or submission logic

- **Code generates queues, AI agents gather context, humans decide.** Never
  add logic that submits to Wikidata autonomously. Every edit path goes
  through the `decision` table.
- Checks operate on the **local model only** (no live SPARQL inside checks).
  The local DB is for queue generation; live entity JSON must be re-fetched
  before any actual edit (research.md §10.1).
- `position` = item used as a value of P39. The high-precision subset is
  `P31 = Q294414` (public office); research.md §1.2 explains why checks
  restrict to it and why that is *not* the complete political universe.
- Do not "fix" missing metadata that is legitimately absent (generic roles
  like president/senator must not get a single country). research.md §2
  and §3.4 list the known traps.
- Adding a new check = add a function + `Check` entry in `checks.py`,
  following the existing pattern (return `(qid, details-dict)` rows).

## External-service gotchas (learned the hard way)

- WDQS truncates responses around ~18 MB / times out on big aggregations —
  always paginate with stable `ORDER BY ... LIMIT/OFFSET`, and retry on
  429/5xx. Never `DISTINCT`+`OFFSET` huge sets without testing.
- `wbgetentities` with `formatversion=2` returns `entities` as a **map
  keyed by QID**, not a list.
- `executemany` in DuckDB errors on empty parameter lists — guard.
- SPARQL braces collide with Python `.format()` — use token replacement.

## Code style

- Python 3.12+, Ruff defaults, type hints, small modules.
- Keep dependencies minimal; this is a local CLI (DuckDB + httpx + typer +
  rich). No web framework, no Postgres — deliberately unlike PoliLoom.

## Borrowing from PoliLoom

[PoliLoom](https://github.com/opensanctions/poliloom) (local checkout:
~/projects/poliloom) has reusable patterns for: Wikidata JSON-dump streaming
import (`poliloom/poliloom/importer/`), hierarchy P279 closure, and
statement submission with OAuth (`poliloom/poliloom/wikidata/statement.py`,
`poliloom/poliloom/api/auth.py`). Crib from it for roadmap items, but keep
this repo self-contained and serverless.
