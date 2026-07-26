# AGENTS.md

`positions` is a personal human-in-the-loop queue for improving political
position items on Wikidata. An LLM agent researches and queues proposed
edits; a human reviews them in the TUI and only an explicit accept submits.

The local SQLite database holds **proposed edits only** — there is no
Wikidata mirror and no sync. The agent queries Wikidata itself — SPARQL
against the QLever mirror, which follows the change stream and is seconds
behind live — plus the web (and the REST API for live entity state when
building patches). The server is the only authority on staleness: each
patch's own `test` ops are evaluated against live state at accept time,
never by the client. Domain knowledge lives in pi skills under
`.pi/skills/`, not in code.

## Commands

```bash
uv sync
uv run positions queue proposals.json   # enqueue proposed edits (agent-facing)
uv run positions list --status all      # pending queue and tombstones
uv run positions show <id>              # full proposal detail
uv run positions                        # TUI: accept/discard queued proposals
```

Accepting submits to Wikidata and requires `WIKIDATA_ACCESS_TOKEN`; see
`.env.example`. Use a separate `--db` file for tests and never accept
an edit during automated verification.

## Project structure

```text
src/positions/
  cli.py         Typer commands (queue/list/show/drop) and TUI entry point
  tui.py         Textual review loop over pending proposals
  proposals.py   queue payload: patch/create validation and display
  wikidata.py    authenticated PATCH/POST submission to the Wikibase REST API
  db.py          SQLAlchemy/SQLite proposal queue and tombstones
.pi/skills/
  propose-edits/             agent workflow: research and queue
  wikidata-querying/         QLever SPARQL mirror and live API reference
  wikidata-political-model/  political data modeling reference
  wikidata-labels/           labels, aliases, mul, and fallback reference
```

## Invariants

- A human must explicitly accept every edit. Never add unattended submission;
  the agent's only write path is `positions queue`.
- A proposal is one of two kinds, each submitted verbatim to the Wikibase
  REST API — atomically or not at all: a **patch** (one entity QID plus an
  RFC 6902 JSON Patch to `PATCH /v1/entities/items/{id}`) or a **create**
  (one new-item document to `POST /v1/entities/items`). Validation is
  structural only; payload discipline (test pins, deprecate-vs-remove,
  existence checks before creates) is agent guidance in the skills.
- There is no client-side pre-flight check before submission. For a patch,
  the server evaluates it (including its `test` ops) against live state; a
  404/409/412 means live state drifted, so mark the proposal stale —
  never force an edit through. A create has no live state to pin and
  cannot go stale; guarding against duplicate items is review discipline,
  not code.
- Terminal proposal states (submitted/rejected/stale) stay in the table as
  tombstones keyed by content fingerprint, so a decided edit is never
  proposed again.
- Keep the project local and serverless with minimal dependencies.
- Keep only the current schema and API shapes in the code. Do not add
  migrations, backward-compatibility branches, or legacy fallbacks: when the
  schema changes, delete the local SQLite file and requeue.

## Implementation notes

- Submission maps responses: patch 200 → submitted, 404/409/412 → stale;
  create 201 → submitted (the response body's `id` becomes the proposal's
  entity). Anything else — rejection, rate limit, server error — is
  failed: the error is shown in the TUI and the proposal stays pending for
  the human to re-approve or discard; there is no automatic retry. No CSRF
  token or baserevid — the OAuth 2.0 bearer suffices, and a patch's own
  `test` ops are the concurrency guard.
- Use Python 3.12+, type hints, and Ruff defaults.
