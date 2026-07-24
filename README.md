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
                   positions.duckdb ◀──── you: positions check / show / review
                          │
              ┌───────────┼───────────────┐
              ▼           ▼               ▼
        audit checks   agent bridge    submitter
        (SQL queues)   (context out,   (QuickStatements /
                        proposals in)   API edits, logged)
```

- **Sync** builds a local world model. All of research.md's SPARQL audits
  become instant local SQL.
- **Checks** are named queries that produce review queues (`queue` table).
  New checks are just SQL — the whole point of the local model.
- **Decisions** (approve/reject/skip) are recorded locally. Nothing is ever
  submitted to Wikidata without a human decision.
- **Agents** gather context (official sources, translations, parent-class
  candidates) and write *proposals*. Deterministic rules validate them.
- The live Wikidata API is re-fetched before any submission; the local DB
  is for queue generation, never the source of truth at edit time.

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

## Roadmap

1. **World model** (this): positions universe + claims, local checks.
2. **Holder statements**: import all P39 statements with qualifiers
   (start/end, term, cabinet, district, group, references) — from the
   Wikidata JSON dump, reusing PoliLoom's importer patterns. Enables
   research.md §4 (P1308→P39 reconciliation) and §8 (statement quality).
3. **Governments layer**: cabinets, legislatures, agencies (Govdirectory
   model) — staleness checks like "jurisdiction has >1 'current' cabinet"
   or missing P576/P9798.
4. **Review loop**: TUI serving queue items with full context; approve →
   QuickStatements file or direct API edit; revision IDs logged for
   rollback.
5. **Freshness monitor**: scheduled re-sync, diff against official sources
   scraped by agents — "Wikidata thinks X, government site says Y".
