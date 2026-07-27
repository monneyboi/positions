# AGENTS.md

`positions` is a personal human-in-the-loop queue for improving political
position items on Wikidata. The goal is complete, well-modeled coverage
of the world's political *positions* at every level of government —
office items (the values of `position held (P39)`), the institutions
they belong to, their jurisdictions, and their lifecycle — from the
national spine down through regions and municipalities to
special-purpose bodies such as water boards. Politicians and their P39
statements are out of scope: mapping officeholders to offices is
[poliloom](https://github.com/opensanctions/poliloom)'s domain, not
this project's. An LLM agent researches and queues proposed edits in
batches; a human reviews each batch in the TUI and only an explicit
accept submits.

The local SQLite database holds **proposed edits only** — there is no
Wikidata mirror and no sync. The agent queries Wikidata itself — SPARQL
against the QLever mirror, which follows the change stream and is seconds
behind live — plus the web (and the REST API for live entity state when
building edits). The server is the only authority on staleness: each
edit's target is resolved against live state at accept time, never by
the client. Domain knowledge lives in pi skills under `.pi/skills/`, not
in code.

## Commands

```bash
uv sync
uv run positions queue proposals.json   # enqueue batches of proposed edits (agent-facing)
uv run positions list --status all      # pending queue and tombstones
uv run positions show <id>              # full proposal detail
uv run positions                        # TUI: accept/discard queued batches
```

Accepting submits to Wikidata and requires `WIKIDATA_ACCESS_TOKEN`; see
`.env.example`. Use a separate `--db` file for tests and never accept
an edit during automated verification.

## Project structure

```text
src/positions/
  cli.py            Typer commands (queue/list/show/drop) and TUI entry point
  tui.py            Textual review loop over pending batches
  proposals.py      queue payload: batch and edit validation (spec-driven)
  spec.py            the allowlist; data/operations.json is the OpenAPI spec,
                     filtered to allowed operations (`uv run python -m positions.spec`)
  wikidata.py       authenticated verbatim submission to the Wikibase REST API
  db.py             SQLAlchemy/SQLite proposal queue and tombstones
.pi/skills/
  propose-edits/             agent workflow: research and queue
  wikidata-querying/         QLever SPARQL mirror and live API reference
  wikidata-political-model/  position-item modeling reference: the country
                             spine of offices, institutions, jurisdictions
  wikidata-labels/           labels, aliases, mul, and fallback reference
```

## Invariants

- A human must explicitly accept every edit. Never add unattended submission;
  the agent's only write path is `positions queue`.
- Edits are queued in **batches**: one rationale plus one or more edits,
  which the human reviews and decides as a unit. An edit is one Wikibase
  REST API operation, submitted verbatim — atomically or not at all: an
  `operationId` on the allowlist in `spec.py`, plus the `params` (path
  parameters) and `body` (request body) the operation declares in the
  OpenAPI spec (extracted into `data/operations.json`). The rationale is the only queue metadata;
  sourcing lives in the payload itself (statement references). Validation
  is structural only, read from the spec: allowed operation, exact path
  params matching their patterns, declared body fields. Payload discipline
  (deprecate-vs-remove, references on added statements, existence checks
  before creates) is agent guidance in the skills.
- Merging items is out of scope: the REST API has no merge operation
  (redirects are only created as a side effect of the Action API's
  merge), and emulating one from statement edits would leave a crippled
  duplicate with no redirect. Duplicate findings are reported to the
  human, never queued.
- There is no client-side pre-flight check before submission; the server's
  response decides the outcome. Edits address stable identities — item
  ids, statement GUIDs, language codes, never positional indices (the
  item-level `patchItem` is not on the allowlist) — so drift between
  queueing and accept surfaces as a loud 404/409/412 and the edit goes
  stale, never a silent wrong-target edit. A create (`addItem`,
  `addItemStatement`) has no live state to pin and cannot go stale;
  guarding against duplicates is review discipline, not code.
- Terminal edit states (submitted/rejected/stale) stay in the table as
  tombstones keyed by content fingerprint, so a decided edit is never
  proposed again.
- Keep the project local and serverless with minimal dependencies.
- Keep only the current schema and API shapes in the code. Do not add
  migrations, backward-compatibility branches, or legacy fallbacks: when the
  schema changes, delete the local SQLite file and requeue.

## Implementation notes

- Submission maps responses uniformly for every operation: 200/201 →
  submitted (a response body `id` — a create's new QID or statement GUID —
  becomes the edit's entity); 404/409/412 → stale. A batch accept submits
  its edits sequentially, each with its own outcome. Anything else —
  rejection, rate limit, server error — is failed: the error is shown in
  the TUI and the edit stays pending for the human to re-approve or
  discard. Submission is just the OAuth 2.0 bearer plus the verbatim
  params and body; addressing edits by stable identity (never array
  indices) is the concurrency guard.
- Use Python 3.12+, type hints, and Ruff defaults.
