---
name: propose-edits
description: Queue proposed Wikidata edits for human review using the positions CLI. Use whenever you have found a concrete improvement to a Wikidata item (especially political positions, institutions, or jurisdictions) that should be verified and submitted by a human. Never edit Wikidata directly — always queue.
---

# Proposing Wikidata edits with positions

`positions` is a human-in-the-loop edit queue. You research and queue
batches of proposed edits; a human reviews each batch in the TUI and only
their explicit accept submits to Wikidata, where the server applies each
edit atomically — one Wikibase REST API operation per edit.

**You never edit Wikidata yourself. Your output is always a queued batch.**

## Scope

The allowlist in the payload schema below is the complete vocabulary —
an edit is one of those operations or it cannot be queued. Two kinds of
things fall outside:

**The REST API cannot do it.** There is no merge operation, no way to
delete an item, and no way to create a redirect (Wikidata redirects
exist only as a side effect of the Action API's item merge). So:

- **Merging duplicate items is out of scope.** Never emulate a merge by
  queueing edits that copy statements off the duplicate — without the
  redirect that leaves a crippled duplicate behind, which is worse than
  doing nothing. When you find a duplicate pair, name both QIDs in your
  report and leave the merge to the human (the on-wiki Merge gadget).
- A finding that needs an item deleted is likewise report-only.

**Excluded by policy, not by the API.** The item-level `patchItem`
(positional statement paths drift onto the wrong statement), the
wholesale `replace*Statement` operations, and all property and sitelink
operations are absent from the allowlist on purpose. If a finding
genuinely needs one of these, report it — do not force it into an
allowed shape.

## Workflow

1. **Find candidates** with SPARQL against the QLever mirror (see the
   `wikidata-querying` skill). Follow the modeling rules in the
   `wikidata-political-model` skill.
2. **Ground the payload in live data.** Fetch every target item from the
   Wikibase REST API:

   ```bash
   curl -s https://www.wikidata.org/w/rest.php/wikibase/v1/entities/items/Q123456
   ```

   This response is where statement GUIDs (`Q123456$1B7C…`) come from —
   every `patchItemStatement`/`deleteItemStatement` addresses one
   statement by this id. Never write GUIDs from memory or from SPARQL
   results.

   For an `addItem` create, the target does not exist — that is the
   point. Verify it really doesn't (QLever queries plus the REST item
   search, checking labels and near-duplicates).
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
4. **Report** what you queued and why, so the human can review quickly
   — plus any out-of-scope findings you did *not* queue (see Scope),
   e.g. duplicate items that need merging.

## Payload schema

The payload is one batch object (a bare list of batch objects also
works). A batch is one `rationale` plus a non-empty `edits` list — the
human reviews and decides the batch as a unit. An edit names ONE
operation from the allowlist by its `operationId`, plus the `params`
(path parameters) and `body` (request body) that operation declares in
the Wikibase REST API OpenAPI spec; both go verbatim into the API call.
The `rationale` is the only queue metadata.

| operationId | what it does | params | body |
|---|---|---|---|
| `patchItemStatement` | modify one statement (rank, value, qualifiers, references) | `item_id`, `statement_id` | `patch` (RFC 6902, statement-relative paths) |
| `addItemStatement` | add one new statement to an item | `item_id` | `statement` |
| `deleteItemStatement` | delete one statement | `item_id`, `statement_id` | — |
| `addItem` | create a new item | — | `item` |
| `replaceItemLabel` | set a label in one language | `item_id`, `language_code` | `label` |
| `deleteItemLabel` | remove a label in one language | `item_id`, `language_code` | — |
| `replaceItemDescription` | set a description | `item_id`, `language_code` | `description` |
| `deleteItemDescription` | remove a description | `item_id`, `language_code` | — |
| `addItemAliasesInLanguage` | add aliases in one language | `item_id`, `language_code` | `aliases` (list) |

```json
{
  "rationale": "Kalle Kankkonen was never minister per the official gazette (https://example.org/gazette); the P39 statement on Q123456 is wrong, and his actual term ended 2023-06-20 per https://example.org/cabinet.",
  "edits": [
    {
      "operationId": "patchItemStatement",
      "params": {"item_id": "Q123456", "statement_id": "Q123456$1B7C9F2E-…"},
      "body": {"patch": [
        {"op": "replace", "path": "/rank", "value": "deprecated"},
        {"op": "add", "path": "/qualifiers/-", "value": {
          "property": {"id": "P2241"},
          "value": {"type": "value", "content": "Q…"}
        }}
      ]}
    },
    {
      "operationId": "patchItemStatement",
      "params": {"item_id": "Q123456", "statement_id": "Q123456$8F2E1B7C-…"},
      "body": {"patch": [
        {"op": "add", "path": "/qualifiers/-", "value": {
          "property": {"id": "P582"},
          "value": {"type": "value", "content": {
            "time": "+2023-06-20T00:00:00Z", "precision": 11,
            "calendarmodel": "http://www.wikidata.org/entity/Q1985727"}}
        }},
        {"op": "add", "path": "/references/-", "value": {"parts": [
          {"property": {"id": "P854"},
           "value": {"type": "value", "content": "https://example.org/cabinet"}},
          {"property": {"id": "P813"},
           "value": {"type": "value", "content": {
             "time": "+2026-03-12T00:00:00Z", "precision": 11,
             "calendarmodel": "http://www.wikidata.org/entity/Q1985727"}}}
        ]}}
      ]}
    },
    {
      "operationId": "addItemStatement",
      "params": {"item_id": "Q654321"},
      "body": {"statement": {
        "property": {"id": "P39"},
        "value": {"type": "value", "content": "Q999888"},
        "rank": "normal",
        "references": [{"parts": [
          {"property": {"id": "P854"},
           "value": {"type": "value", "content": "https://example.org/cabinet"}}
        ]}]
      }}
    },
    {
      "operationId": "replaceItemLabel",
      "params": {"item_id": "Q999888", "language_code": "fi"},
      "body": {"label": "Suomen valtiovarainministeri"}
    }
  ]
}
```

- `rationale` (required, one per batch): what the human verifies
  against — why these edits are correct. Write human-readable labels,
  not just QIDs, and name the official pages you relied on: for edits
  that remove or deprecate statements this text is the only place the
  evidence lives.
- `params`: exactly the operation's path parameters, named as in the
  spec (`item_id`, `statement_id`, `language_code`). Get statement GUIDs
  from the live GET — never from memory.
- `body`: the operation's request body. The spec also permits `tags`,
  `bot`, `comment` — leave them out; they are not the point of an edit.

Edits in one batch are submitted as separate API calls in queue order —
they must be **independent**: an edit cannot reference an `addItem`'s
not-yet-assigned QID, so "create item, then edit it" is two runs, not
one batch.

## Editing statements

Each statement edit addresses **one statement by its GUID** with
statement-relative paths — never positional indices into an item's
statement arrays (the item-level `patchItem` is not allowed, on purpose:
array order is not stable, and an index that drifts silently edits the
wrong statement). If the statement is gone or the item was merged when
the human accepts, the server 404s and the edit goes stale instead of
editing the wrong thing.

- **Deprecate, don't remove**, statements that are wrong but have
  history (a former officeholder value, a superseded jurisdiction):
  `{"op": "replace", "path": "/rank", "value": "deprecated"}`, ideally
  with a reason (P2241) qualifier. See the `wikidata-political-model`
  skill for the modeling rules. Reserve `deleteItemStatement` for clear
  junk, vandalism, and exact duplicates.
- **Paths are statement-relative**: `/rank`, `/value/content`,
  `/qualifiers/…`, `/references/…`. Appends use `-`:
  `/qualifiers/-`, `/references/-`.
- **Statement shape** (REST v1): `property.id`, `value.type` +
  `value.content`, `rank`, `qualifiers`, `references`. For item values,
  `content` is the plain QID string; for times, an object with `time`,
  `precision`, `calendarmodel`. The full schema lives in the OpenAPI
  spec: <https://doc.wikimedia.org/Wikibase/master/js/rest-api/>
- **Group what belongs together.** Several changes to the SAME statement
  (deprecate its rank AND add the end-date qualifier AND its reference)
  go in ONE patch so they apply atomically. Changes to different
  statements are separate edits.
- **New statements** are `addItemStatement` edits, one statement per
  edit, each carrying its own reference (below).
- No `test` pins are needed — the GUID is the pin. If you do something
  unusual like removing one qualifier from the middle of a list, prefer
  rebuilding via deprecate+add over index surgery.

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
  pairs) — see the payload example above.

## Creating items

An `addItem` edit is one new-item document sent verbatim to
`POST /v1/entities/items`. Nothing exists to pin, so the guards are your
research and the human's review:

- **Prove absence first.** Search QLever and the REST item search
  (`/v1/search/items?q=…`) for the label and close variants. Wikidata
  never blocks a duplicate; your rationale must say why the item is
  missing, and name what you searched so the reviewer can double-check.
- **Model it completely enough to be useful.** At minimum an `en` label
  and description (see the labels skill), `P31`, and the jurisdiction
  statements (`P17`/`P1001`) the political-model skill requires for the
  item's class. A bare item with one statement is a reject.
- **Everything in one create.** Statements that belong to the item all
  go in its `item` document — don't queue follow-up edits to "finish" an
  item behind a separate human accept.
- **Shapes are the REST v1 shapes from the spec:**
  `labels`/`descriptions` are plain strings per language, `aliases` are
  lists of strings, and statements are the same objects an
  `addItemStatement` body carries.

## Labels, descriptions, aliases

Use the dedicated operations (`replaceItemLabel`,
`replaceItemDescription`, `addItemAliasesInLanguage`, and the `delete*`
variants) — never a statement patch for these. Follow the
`wikidata-labels` skill: when `mul` applies, prefer it; a replace is a
plain set, so check the live value first and say in the rationale what
you are changing from.

## Useful commands

```bash
uv run positions list [--status pending|submitted|rejected|stale|all]
uv run positions show <id>     # full edit detail, including its batch rationale
uv run positions queue <file>  # enqueue; duplicates of known fingerprints are skipped
```

The human runs `uv run positions` to review. You never do.
