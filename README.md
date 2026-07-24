# positions

A personal, low-level tool for making Wikidata the definitive source for
political positions and governments — across **all** countries.

Where [PoliLoom](https://github.com/opensanctions/poliloom) is a community
web app whose unit of work is the *politician*, this is a local CLI whose
unit of work is the *position*: its modeling quality, its holders, its
freshness.

See `research.md` for the audit this tool operationalizes.

## Architecture

```
Wikidata ──WDQS──▶ position universe (all values of P39, with usage counts)
        ──API────▶ entity claims, labels, descriptions (positions + related)
                          │
                          ▼
                   positions.duckdb
                    │           │
                    ▼           ▼
              audit checks    queue + decision tables
              (SQL over the   (you: positions check / queue / show)
               local model)
```

- **Sync** builds a local world model. All of research.md's SPARQL audits
  become instant local SQL.
- **Checks** are named queries that produce review queues (`queue` table).
  New checks are just SQL — the whole point of the local model.
- **Decisions** (approve/reject/skip) are recorded locally (`decision`
  table). Nothing is ever submitted to Wikidata without a human decision.

Design constraints that any future component must keep: code generates
queues, AI agents may gather context and draft proposals, but every edit
decision is human; and the live Wikidata API is re-fetched before any
edit — the local DB is for queue generation, never the source of truth
at edit time.

## Usage

```bash
uv sync
uv run positions sync            # full universe (~30 min first time)
uv run positions sync --limit 500   # quick test slice
uv run positions check           # run all checks, refresh queues
uv run positions check jurisdiction-backfill
uv run positions show Q133268398
```

## Checks implemented

| Check | research.md | What it finds |
|---|---|---|
| `jurisdiction-backfill` | §3 | Public offices whose P361 body supplies missing P17/P1001 |
| `missing-p279` | §5 | Used public offices with no subclass of |
| `missing-en-label` | §6 | Used public offices with no English label |
| `missing-en-description` | §6 | Used public offices with no English description |
| `list-valued` | §7 | Wikimedia list items used as P39 values |

## Planned work

Tracked as [GitHub issues](https://github.com/monneyboi/positions/issues) —
the issue tracker is the single source of truth for what doesn't exist yet.
