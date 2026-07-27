# positions

A small human-in-the-loop queue for improving political position items
on Wikidata — the offices that are the values of `position held (P39)`:
their institutions, jurisdictions, and lifecycle. The goal is complete,
well-modeled coverage of the world's political offices. Politicians and
their P39 statements are out of scope — that's
[poliloom](https://github.com/opensanctions/poliloom).

An agent (pi, with the skills in `.pi/skills/`) researches Wikidata and the
web and queues proposed edits as JSON, in batches of similar changes under
one rationale. The local database holds **proposed
edits only** — no Wikidata mirror. A human reviews each batch in the TUI;
only an explicit accept submits to Wikidata, where each edit is one
Wikibase REST API operation applied atomically, addressed by stable
identity (item id, statement GUID, language code) rather than positional
paths.

## How it works

1. The agent finds improvements (QLever SPARQL mirror, official sources)
   and runs `uv run positions queue proposals.json`.
2. `positions queue` validates the payload structurally against the
   OpenAPI spec (filtered to the allowed operations): an allowed
   `operationId`, its path params, its body fields, plus the batch
   rationale) and stores each edit. Edits
   already known — pending, submitted, rejected, or stale — are skipped by
   fingerprint, so rejected ideas are never proposed again.
3. Running `positions` opens the review TUI: accept submits each edit of
   the batch verbatim to the Wikibase REST API; discard leaves tombstones.
   If live state drifted so the target is gone or conflicts (404/409/412),
   the edit is marked stale instead of editing; any other failure is shown
   in the TUI and the edit stays pending for another decision.

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
names one Wikibase REST API operation by its `operationId` from the
allowlist (`addItem`, `addItemStatement`, `patchItemStatement`,
`deleteItemStatement`, `replaceItemLabel`, `deleteItemLabel`,
`replaceItemDescription`, `deleteItemDescription`,
`addItemAliasesInLanguage`) plus the `params` (path parameters) and
`body` (request body) that operation declares in the OpenAPI spec. The
rationale is the only metadata — sourcing lives in the payload itself as
statement references.

```json
{
  "rationale": "…why these edits are correct…",
  "edits": [
    {
      "operationId": "patchItemStatement",
      "params": {"item_id": "Q123456", "statement_id": "Q123456$1B7C…"},
      "body": {"patch": [
        {"op": "replace", "path": "/rank", "value": "deprecated"}
      ]}
    },
    {
      "operationId": "addItemStatement",
      "params": {"item_id": "Q123456"},
      "body": {"statement": {"property": {"id": "P576"}, "value": {"type": "value", "content": {"time": "+1935-01-01T00:00:00Z", "precision": 9}}, "rank": "normal", "references": [{"parts": [{"property": {"id": "P854"}, "value": {"type": "value", "content": "https://…"}}]}]}}
    },
    {
      "operationId": "addItem",
      "body": {"item": {
        "labels": {"en": "Minister of Finance of Finland"},
        "descriptions": {"en": "political office in Finland"},
        "statements": {"P31": [{"property": {"id": "P31"}, "value": {"type": "value", "content": "Q…"}, "rank": "normal"}]}
      }}
    }
  ]
}
```

`params` fill the operation's path template and `body` goes verbatim
into the request; when a create is accepted, the new QID or statement
GUID is recorded on the edit. Statement patches address one statement by
its GUID with statement-relative paths (`/rank`, `/value/content`,
`/qualifiers/-`, `/references/-`) — no positional indices anywhere. See
`.pi/skills/propose-edits/SKILL.md` for the full agent contract.

## Research cache

`cache/` (gitignored, disposable) holds per-country surveys of how
political systems are currently modeled on Wikidata, one directory per
country QID (`cache/countries/q183/`). A survey is a set of numbered
`.sparql`/`.json` query-result pairs plus a README of findings, produced
by the prompt template `.pi/prompts/survey-country.md`.

Run one headless, fresh per country (takes the country QID as its only
argument; rebuilds that country's directory from scratch):

```bash
PI="pi -p --approve --provider openai-codex --model gpt-5.6-terra --thinking medium"
$PI "/survey-country Q183"
# several, in parallel:
for q in Q183 Q142 Q30; do $PI "/survey-country $q" & done; wait
```

Each run saves a named-by-date session (browse with `pi -r`, export with
`/export`) — that session file is the run record, so don't pass
`--no-session`. Or invoke `/survey-country Q183` in an interactive pi
session. Surveys
are research artifacts: no Wikidata edits, nothing queued — read them
together and decide what to do.
