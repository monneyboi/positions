# positions

A small human-in-the-loop queue for improving political positions on Wikidata.

An agent (pi, with the skills in `.pi/skills/`) researches Wikidata and the
web and queues proposed edits as JSON. The local database holds **proposed
edits only** — no Wikidata mirror. A human reviews each proposal in the TUI;
only an explicit accept submits to Wikidata, where the proposal's own JSON
Patch is evaluated atomically against live state.

## How it works

1. The agent finds improvements (QLever SPARQL mirror, official sources)
   and runs `uv run positions queue proposals.json`.
2. `positions queue` validates the payload structurally (it is an RFC 6902
   JSON Patch plus review metadata) and stores each proposal. Edits already
   known — pending, submitted, rejected, or stale — are skipped by
   fingerprint, so rejected ideas are never proposed again.
3. Running `positions` opens the review TUI: accept POSTs the patch
   verbatim to the Wikibase REST API; discard leaves a tombstone. If live
   state drifted so the patch no longer applies (404/409/412), the
   proposal is marked stale instead of editing.

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
      "patch": [
        {"op": "test", "path": "/statements/P39/2/id", "value": "Q123456$…"},
        {"op": "replace", "path": "/statements/P39/2/rank", "value": "deprecated"},
        {"op": "add", "path": "/statements/P17/-", "value": {"property": {"id": "P17"}, "value": {"type": "value", "content": "Q33"}, "rank": "normal"}}
      ],
      "comment": "deprecate wrong officeholder; add country Finland",
      "rationale": "…why this is correct…",
      "sources": ["https://…"]
    }
  ]
}
```

One proposal edits one entity; `patch` and `comment` go verbatim into the
Wikibase REST API's `PATCH /v1/entities/items/{id}` call. `rationale` is
required when the patch changes existing state.
See `.pi/skills/propose-edits/SKILL.md` for the full agent contract.
