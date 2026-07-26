---
name: propose-edits
description: Queue proposed Wikidata edits for human review using the positions CLI. Use whenever you have found a concrete improvement to a Wikidata item (especially political positions, institutions, or jurisdictions) that should be verified and submitted by a human. Never edit Wikidata directly — always queue.
---

# Proposing Wikidata edits with positions

`positions` is a human-in-the-loop edit queue. You research and propose;
a human reviews each proposal in the TUI and only their explicit accept
submits to Wikidata, where the server applies your JSON Patch atomically
against live state.

**You never edit Wikidata yourself. Your output is always a queued proposal.**

## Workflow

1. **Find candidates** with SPARQL against the QLever mirror (see the
   `wikidata-querying` skill). Follow the modeling rules in the
   `wikidata-political-model` skill.
2. **Fetch the target item** from the Wikibase REST API:

   ```bash
   curl -s https://www.wikidata.org/w/rest.php/wikibase/v1/entities/items/Q123456
   ```

   This response is the document your patch addresses: positional paths
   like `/statements/P39/2` index into its `statements` arrays, and each
   statement's `id` is the strongest pin for a `test` op. Never write
   paths from memory or from SPARQL results — indices and ids come from
   this GET, and only from this GET.
3. **Queue the payload** (schema below):

   ```bash
   uv run positions queue proposals.json
   # or pipe: cat proposals.json | uv run positions queue
   ```

   The queue skips payloads whose fingerprint is already known in any
   status, so a decided edit is never re-queued — read the skip output.
4. **Report** what you queued and why, so the human can review quickly.

## Payload schema

A JSON object `{"proposals": [...]}` (a bare list also works). Each
proposal edits ONE entity. `patch` and `comment` go verbatim into the
Wikibase REST API's `PATCH /v1/entities/items/{id}` call; the rest is
review metadata for the human.

```json
{
  "proposals": [
    {
      "entity": "Q123456",
      "patch": [
        {"op": "test", "path": "/statements/P39/2/id", "value": "Q123456$a1b2-…"},
        {"op": "replace", "path": "/statements/P39/2/rank", "value": "deprecated"},
        {"op": "test", "path": "/labels/en", "value": "Minister of Finance"},
        {"op": "replace", "path": "/labels/en", "value": "Minister of Finance of Finland"},
        {"op": "add", "path": "/statements/P17/-", "value": {
          "property": {"id": "P17"},
          "value": {"type": "value", "content": "Q33"},
          "rank": "normal"
        }}
      ],
      "comment": "deprecate wrong officeholder; fix en label; add country Finland",
      "rationale": "Q… was never minister per the official gazette; label per labels skill.",
      "sources": ["https://example.org/official-gazette", "https://www.wikidata.org/wiki/Q123456"]
    }
  ]
}
```

- `patch` (required): an RFC 6902 JSON Patch. All six ops are allowed:
  `add`, `remove`, `replace`, `move`, `copy`, `test`.
- `comment` (required): becomes the Wikidata edit summary — include
  human-readable labels, not just QIDs.
- `rationale`: what the human verifies against. **Required whenever the
  patch changes existing state** (any `remove`/`replace`/`move`/`copy`);
  always cite official sources or the Wikidata items you relied on.
- `sources`: URLs for the reviewer.

## Writing good patches

The server evaluates the patch **in order, atomically**: either every op
applies or the edit is rejected (a failed `test` → 409 → the proposal
goes stale; the human never sees a partial edit).

- **Pin what you touch.** Before a `remove`, `replace`, or `move`/`copy`
  `from` at a positional path, add a `test` on that statement's `id` (or
  on the exact old label/description before replacing it). If someone
  edits the item between your research and the human's accept, indices
  may shift — the pin turns a wrong-target edit into a harmless 409.
- **Appends use `-`**: `{"op": "add", "path": "/statements/P17/-", …}`.
- **Statement shape** (REST v1): `property.id`, `value.type` +
  `value.content`, `rank`, `qualifiers`, `references`. For item values,
  `content` is the plain QID string; for times, an object with `time`,
  `precision`, `calendarmodel`. Copy shapes from the GET response, not
  from memory. Full reference:
  <https://doc.wikimedia.org/Wikibase/master/js/rest-api/>
- **Deprecate, don't remove**, statements that are wrong but have
  history (a former officeholder value, a superseded jurisdiction):
  `replace` the `rank` with `"deprecated"`. Reserve `remove` for clear
  junk, vandalism, and duplicates. See the `wikidata-political-model`
  skill for the modeling rules.
- **`move` for wrong-property fixes** — it keeps the statement intact
  instead of remove+add.
- **Indices shift as the patch applies.** If one patch removes several
  statements from the same property, remove highest index first, or
  pin each by `id` before removing.
- **Group what belongs together.** Statements that only make sense as a
  unit (e.g. a paired P17 + P1001, an end date plus its successor's
  start date) go in ONE proposal so they apply atomically.

## Useful commands

```bash
uv run positions list [--status pending|submitted|rejected|stale|all]
uv run positions show <id>     # full proposal detail
uv run positions queue <file>  # enqueue; duplicates of known fingerprints are skipped
```

The human runs `uv run positions` to review. You never do.
