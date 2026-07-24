# positions

A local CLI for reviewing and improving political position items on Wikidata.
The unit of work is a position used as a `position held (P39)` value, rather
than a politician.

The current workflow handles one deterministic cleanup: public offices missing
both `country (P17)` and `applies to jurisdiction (P1001)` can inherit those
values from their `part of (P361)` body when the relationship is unambiguous.
See `research.md` §3 for the modeling rationale and safeguards.

## How it works

1. `sync` discovers P39 values through WDQS and stores their Wikidata entities
   and one-hop related entities in `positions.duckdb`. Later syncs only fetch
   entities whose revisions changed.
2. `propose` stores eligible P17/P1001 pairs as pending local claims.
3. Running `positions` opens an interactive review loop, ordered by P39 usage.
   Discard keeps a local tombstone. Accept re-fetches the position and its body,
   verifies the proposal against live Wikidata, and submits both claims in one
   edit using revision-based concurrency.

Nothing is submitted without an explicit human acceptance. The local database
is used to find and track proposals, not as the source of truth at edit time.

## Setup

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env
```

A Wikidata OAuth 2.0 access token is only required to accept a proposal. Follow
`.env.example` to configure `WIKIDATA_ACCESS_TOKEN`.

## Usage

```bash
uv run positions sync                 # refresh the full local model
uv run positions sync --limit 500     # small test slice
uv run positions propose              # create pending P17/P1001 proposals
uv run positions                      # review: accept, discard, or quit
uv run positions show Q133268398      # inspect a local entity
```

All commands use `positions.duckdb` by default and accept `--db PATH`.

Future work is tracked in the [GitHub issue tracker](https://github.com/monneyboi/positions/issues).
