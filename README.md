# positions

A small human-in-the-loop queue for improving political positions on Wikidata.

An agent (pi, with the skills in `.pi/skills/`) researches Wikidata and the
web and queues proposed edits as JSON. The local database holds **proposed
edits only** — no Wikidata mirror. A human reviews each proposal in the TUI;
only an explicit accept submits to Wikidata, after a live duplicate check and
with revision-based concurrency.

## How it works

1. The agent finds improvements (WDQS, `wbgetentities`, official sources),
   verifies them against live data, and runs
   `uv run positions queue proposals.json`.
2. `positions queue` validates the payload and stores each proposal. Edits
   already known — pending, submitted, rejected, or stale — are skipped by
   fingerprint, so rejected ideas are never proposed again.
3. Running `positions` opens the review TUI: accept submits the proposal's
   statements in one atomic, `baserevid`-guarded edit; discard leaves a
   tombstone; a live state change marks the proposal stale instead of
   editing.

Nothing is ever submitted without an explicit human accept.

## Setup

```bash
uv sync
cp .env.example .env   # fill in WIKIDATA_ACCESS_TOKEN to accept edits
```

## Commands

```bash
uv run positions queue proposals.json   # enqueue proposed edits (agent-facing)
uv run positions list --status all      # pending queue and tombstones
uv run positions show <id>              # full proposal detail
uv run positions drop <id>              # delete a pending proposal, no tombstone
uv run positions                        # review TUI
uv run positions --db /tmp/smoke.sqlite # any command works on a scratch DB
```

## Proposal JSON

```json
{
  "proposals": [
    {
      "entity": "Q123456",
      "statements": [{"property": "P17", "value": "Q33"}],
      "summary": "Minister of Agriculture of Finland: add country Finland",
      "rationale": "…why this is correct…",
      "sources": ["https://…"]
    }
  ]
}
```

Add-only, item-valued statements; one proposal edits one entity atomically.
See `.pi/skills/propose-edits/SKILL.md` for the full agent contract.
