# positions

A small human-in-the-loop queue for improving political positions on Wikidata.

An agent (pi, with the skills in `.pi/skills/`) researches Wikidata and the
web and queues proposed edits as JSON, in batches of similar changes under
one rationale. The local database holds **proposed
edits only** — no Wikidata mirror. A human reviews each batch in the TUI;
only an explicit accept submits to Wikidata, where each edit's payload is
applied atomically — a patch against live state, guarded by its own
`test` ops.

## How it works

1. The agent finds improvements (QLever SPARQL mirror, official sources)
   and runs `uv run positions queue proposals.json`.
2. `positions queue` validates the payload structurally (a JSON Patch or a
   new-item document per edit, plus the batch rationale) and stores each
   edit. Edits
   already known — pending, submitted, rejected, or stale — are skipped by
   fingerprint, so rejected ideas are never proposed again.
3. Running `positions` opens the review TUI: accept submits each edit of
   the batch
   verbatim to the Wikibase REST API (`PATCH` for a patch, `POST` for a
   create); discard leaves tombstones. If live state drifted so a patch no
   longer applies (404/409/412), the edit is marked stale instead of
   editing; any other failure is shown in the TUI and the edit stays
   pending for another decision.

Nothing is ever submitted without an explicit human accept.

## Setup

```bash
uv sync
cp .env.example .env   # fill in WIKIDATA_ACCESS_TOKEN to accept edits
```

## Commands

```bash
uv run positions queue proposals.json   # enqueue edit batches (agent-facing)
uv run positions list --status all      # pending queue and tombstones
uv run positions show <id>              # full edit detail, incl. batch rationale
uv run positions drop <id>              # delete a pending proposal, no tombstone
uv run positions                        # review TUI
uv run positions --db /tmp/smoke.sqlite # any command works on a scratch DB
```

## Queue JSON

The payload is one batch object (or a list of them): one `rationale`
plus a non-empty `edits` list, reviewed and decided as a unit. An edit
is one of two kinds. A **patch** edits one existing entity; a **create**
makes one new item. The rationale is the only metadata — sourcing lives
in the payload itself as statement references.

```json
{
  "rationale": "…why these edits are correct…",
  "edits": [
    {
      "kind": "patch",
      "entity": "Q123456",
      "patch": [
        {"op": "test", "path": "/statements/P39/2/id", "value": "Q123456$…"},
        {"op": "replace", "path": "/statements/P39/2/rank", "value": "deprecated"},
        {"op": "add", "path": "/statements/P17/-", "value": {"property": {"id": "P17"}, "value": {"type": "value", "content": "Q33"}, "rank": "normal", "references": [{"parts": [{"property": {"id": "P854"}, "value": {"type": "value", "content": "https://…"}}]}]}}
      ]
    },
    {
      "kind": "create",
      "item": {
        "labels": {"en": "Minister of Finance of Finland"},
        "descriptions": {"en": "political office in Finland"},
        "statements": {"P31": [{"property": {"id": "P31"}, "value": {"type": "value", "content": "Q…"}, "rank": "normal"}]}
      }
    }
  ]
}
```

`patch`/`item` go verbatim into the Wikibase REST API's
`PATCH /v1/entities/items/{id}` or `POST /v1/entities/items` call; when a
create is accepted, the new QID is recorded on the edit. See `.pi/skills/propose-edits/SKILL.md` for the
full agent contract.
