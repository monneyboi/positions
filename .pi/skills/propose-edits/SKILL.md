---
name: propose-edits
description: Queue proposed Wikidata edits for human review using the positions CLI. Use whenever you have found a concrete improvement to a Wikidata item (especially political positions, institutions, or jurisdictions) that should be verified and submitted by a human. Never edit Wikidata directly — always queue.
---

# Proposing Wikidata edits with positions

`positions` is a human-in-the-loop edit queue. You research and propose;
a human reviews each proposal in the TUI and only their explicit accept
submits to Wikidata (with a live duplicate check and revision concurrency).

**You never edit Wikidata yourself. Your output is always a queued proposal.**

## Workflow

1. **Find candidates** with SPARQL against the QLever mirror (see the
   `wikidata-querying` skill for the endpoint and how it differs from
   WDQS). Follow the modeling rules in the `wikidata-political-model`
   skill. The mirror follows Wikidata's change stream and is only
   seconds behind; do not re-verify against the live API — the
   authoritative duplicate and staleness check runs at accept time.
2. **Queue the payload** (schema below):

   ```bash
   uv run positions queue proposals.json
   # or pipe: cat proposals.json | uv run positions queue
   ```

   The queue skips payloads whose fingerprint is already known in any
   status, so a decided edit is never re-queued — read the skip output.
3. **Report** what you queued and why, so the human can review quickly.

## Payload schema

A JSON object `{"proposals": [...]}` (a bare list also works). Each
proposal edits ONE entity atomically:

```json
{
  "proposals": [
    {
      "entity": "Q123456",
      "statements": [
        {"property": "P17", "value": "Q33"},
        {"property": "P1001", "value": "Q15634554"}
      ],
      "summary": "Minister of Agriculture of Finland: add country Finland",
      "rationale": "Public office, part of Ministry of Agriculture (Q…) which has exactly this P17/P1001 pair; position has neither.",
      "sources": ["https://www.wikidata.org/wiki/Q123456", "https://example.org/official-page"]
    }
  ]
}
```

Rules:

- Add-only, item-valued statements (`property` = PID, `value` = QID). No
  rank changes, removals, qualifiers, or non-item values yet.
- `summary` is required and becomes the Wikidata edit summary — include
  human-readable labels, not just QIDs.
- `rationale` and `sources` are what the human verifies against. Always
  provide them; cite official sources or the Wikidata items you relied
  on.
- Group statements that only make sense together (e.g. a paired
  P17 + P1001) in one proposal so they are submitted atomically.

## Useful commands

```bash
uv run positions list [--status pending|submitted|rejected|stale|all]
uv run positions show <id>     # full proposal detail
uv run positions queue <file>  # enqueue; duplicates of known fingerprints are skipped
```

The human runs `uv run positions` to review. You never do.
