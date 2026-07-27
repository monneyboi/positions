---
name: propose-edits
description: Queue proposed Wikidata edits for human review using the positions CLI. Use whenever you have found a concrete improvement to a Wikidata item (especially political positions, institutions, or jurisdictions) that should be verified and submitted by a human. Never edit Wikidata directly — always queue.
---

# Proposing Wikidata edits with positions

`positions` is a human-in-the-loop edit queue. You research and queue
batches of proposed edits; a human reviews each batch in the TUI and only
their explicit accept submits to Wikidata, where the server applies each
edit atomically — a patch against live state, or a new item in one shot.

**You never edit Wikidata yourself. Your output is always a queued batch.**

## Workflow

1. **Find candidates** with SPARQL against the QLever mirror (see the
   `wikidata-querying` skill). Follow the modeling rules in the
   `wikidata-political-model` skill.
2. **Ground the payload in live data.** For a patch, fetch the target
   item from the Wikibase REST API:

   ```bash
   curl -s https://www.wikidata.org/w/rest.php/wikibase/v1/entities/items/Q123456
   ```

   This response is the document your patch addresses: positional paths
   like `/statements/P39/2` index into its `statements` arrays, and each
   statement's `id` is the strongest pin for a `test` op. Never write
   paths from memory or from SPARQL results — indices and ids come from
   this GET, and only from this GET.

   For a create, the target does not exist — that is the point. Verify it
   really doesn't (QLever queries plus the REST item search, checking
   labels and near-duplicates), and GET a *similar* existing item to copy
   statement shapes from.
3. **Queue the payload** (schema below). Group edits that stand or fall
   on the same reasoning into ONE batch — one batch, one rationale. Keep
   unrelated findings in separate batches (the payload may be a list of
   batch objects).

   ```bash
   uv run positions queue proposals.json
   # or pipe: cat proposals.json | uv run positions queue
   ```

   The queue skips edits whose fingerprint is already known in any
   status, so a decided edit is never re-queued — read the skip output.
4. **Report** what you queued and why, so the human can review quickly.

## Payload schema

The payload is one batch object (a bare list of batch objects also
works). A batch is one `rationale` plus a non-empty `edits` list — the
human reviews and decides the batch as a unit. An edit is one of two
kinds: a **patch** edits ONE existing entity, a **create** makes ONE new
item. `patch`/`item` go verbatim into the Wikibase REST API's
`PATCH /v1/entities/items/{id}` or `POST /v1/entities/items` call; the
`rationale` is the only metadata.

```json
{
  "rationale": "Q… was never minister per the official gazette (https://example.org/official-gazette); the P39 value points at the wrong office item, and the en label should follow the labels skill.",
  "edits": [
    {
      "kind": "patch",
      "entity": "Q123456",
      "patch": [
        {"op": "test", "path": "/statements/P39/2/id", "value": "Q123456$a1b2-…"},
        {"op": "replace", "path": "/statements/P39/2/rank", "value": "deprecated"},
        {"op": "test", "path": "/labels/en", "value": "Minister of Finance"},
        {"op": "replace", "path": "/labels/en", "value": "Minister of Finance of Finland"},
        {"op": "add", "path": "/statements/P17/-", "value": {
          "property": {"id": "P17"},
          "value": {"type": "value", "content": "Q33"},
          "rank": "normal",
          "references": [{
            "parts": [
              {"property": {"id": "P854"},
               "value": {"type": "value", "content": "https://example.org/ministry-page"}},
              {"property": {"id": "P813"},
               "value": {"type": "value", "content": {
                 "time": "+2026-03-12T00:00:00Z", "precision": 11,
                 "calendarmodel": "http://www.wikidata.org/entity/Q1985727"}}}
            ]
          }]
        }}
      ]
    },
    {
      "kind": "create",
      "item": {
        "labels": {"en": "Minister of Finance of Finland"},
        "descriptions": {"en": "political office in Finland"},
        "statements": {
          "P31": [{
            "property": {"id": "P31"},
            "value": {"type": "value", "content": "Q…"},
            "rank": "normal"
          }]
        }
      }
    }
  ]
}
```

- `rationale` (required, one per batch): what the human verifies
  against — why these edits are correct. Write human-readable labels,
  not just QIDs, and name the official pages you relied on: for edits
  that remove or deprecate statements this text is the only place the
  evidence lives.
- `kind` (required): `"patch"` or `"create"`. A patch has `entity` +
  `patch` (and no `item`); a create has `item` (and neither `entity` nor
  `patch` — the QID is assigned on creation).
- `patch` (required for patches): an RFC 6902 JSON Patch. All six ops are
  allowed: `add`, `remove`, `replace`, `move`, `copy`, `test`.
- `item` (required for creates): the new-item document. At least one of
  `labels`, `descriptions`, `aliases`, `statements`, `sitelinks`.

Edits in one batch are submitted as separate API calls in queue order —
they must be **independent**: a patch cannot reference a create's
not-yet-assigned QID, so "create item, then patch it" is two runs, not
one batch.

## Sourcing statements

Wikidata's rule: statements should say where the data comes from, and
the reference lives **on the statement**, inside your payload — there is
no separate source field in the queue. Keep it simple: this project
cites web sources only.

- **Every statement you add carries a reference** unless it is the kind
  Wikidata leaves unsourced: common knowledge (`instance of: human`),
  obvious `subclass of`, and external-id/authority-control values (the
  value itself links to the source).
- **Two parts are enough**: `reference URL (P854)` pointing at the page
  you actually read, plus `retrieved (P813)` with today's date. Nice
  extras when cheap: `title (P1476)`, `language of work or name (P407)`,
  `archive URL (P1065)`.
- Prefer official sources — parliament and government pages, gazettes,
  election authorities. **Never** cite Wikipedia or use
  `imported from Wikimedia project (P143)`; the community treats those
  as unsourced.
- The REST v1 reference shape is a list of `parts` (property/value
  pairs) — see the P17 example in the payload schema above, and copy
  shapes from a GET response when in doubt.

## Writing good patches

The server evaluates the patch **in order, atomically**: either every op
applies or the edit is rejected (a failed `test` → 409 → the edit
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
  start date) go in ONE patch so they apply atomically.

## Creating items

A create is one new-item document sent verbatim to
`POST /v1/entities/items`. There are no `test` pins — nothing exists to
pin — so the guards are your research and the human's review:

- **Prove absence first.** Search QLever and the REST item search
  (`/v1/search/items?q=…`) for the label and close variants. Wikidata
  never blocks a duplicate; your rationale must say why the item is
  missing, and name what you searched so the reviewer can double-check.
- **Model it completely enough to be useful.** At minimum an `en` label
  and description (see the labels skill), `P31`, and the jurisdiction
  statements (`P17`/`P1001`) the political-model skill requires for the
  item's class. A bare item with one statement is a reject.
- **Everything in one create.** Statements that belong to the item all go
  in its `item` document — don't queue follow-up patches to "finish" an
  item behind a separate human accept.
- **Shapes are the same REST v1 shapes as in GET responses and patches:**
  `labels`/`descriptions` are plain strings per language, `aliases` are
  lists of strings, and statements are the same objects you would `add`
  in a patch. Copy structure from a GET of a similar existing item.

## Useful commands

```bash
uv run positions list [--status pending|submitted|rejected|stale|all]
uv run positions show <id>     # full edit detail, including its batch rationale
uv run positions queue <file>  # enqueue; duplicates of known fingerprints are skipped
```

The human runs `uv run positions` to review. You never do.
