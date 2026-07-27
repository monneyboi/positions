---
name: wikidata-querying
description: How to query Wikidata from this project — the QLever SPARQL mirror (endpoint, calling convention, and how it differs from the official WDQS) plus the live MediaWiki API for authoritative entity state. Use whenever writing or running SPARQL against Wikidata or fetching entity data.
---

# Querying Wikidata

Two read paths with different purposes:

- **Discovery and bulk SPARQL** → the QLever mirror at
  `https://qlever.dev/api/wikidata`. It follows Wikimedia's RDF change
  stream and is near-real-time, while being dramatically faster than the
  official WDQS (queries that time out there in 60 s run here in well
  under a second, with a 600 s timeout). Use it for all candidate
  finding and analysis.
- **Authoritative live state** → the Wikibase REST API at
  `https://www.wikidata.org/w/rest.php/wikibase/v1`. The submission path
  verifies nothing client-side (the patch's own `test` ops are checked
  server-side), so queued proposals need no live pre-check; use this
  when you need authoritative state mid-research or to build a patch.

## Calling the QLever endpoint

Standard SPARQL protocol — POST the raw query:

```bash
curl -s https://qlever.dev/api/wikidata \
  -H "Accept: application/sparql-results+json" \
  -H "Content-type: application/sparql-query" \
  --data 'PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
SELECT ?pos (COUNT(?person) AS ?holders) WHERE {
  ?person wdt:P39 ?pos .
  FILTER NOT EXISTS { ?pos wdt:P17 ?country }
} GROUP BY ?pos ORDER BY DESC(?holders) LIMIT 50'
```

CSV, TSV, XML, and Turtle are available via the `Accept` header;
`application/qlever-results+json` adds runtime and query-plan metadata.
The web UI at `https://qlever.dev/wikidata` has context-sensitive
autocompletion and live query analysis — handy for developing a query
before scripting it.

## Differences from the official WDQS

Most SPARQL examples on the web target WDQS. When porting them:

- **Declare every prefix yourself.** WDQS pre-registers `wd:`, `wdt:`,
  `p:`, `ps:`, `wikibase:`, `schema:`, etc.; QLever rejects undeclared
  prefixes. Standard block:

  ```sparql
  PREFIX wd:       <http://www.wikidata.org/entity/>
  PREFIX wdt:      <http://www.wikidata.org/prop/direct/>
  PREFIX p:        <http://www.wikidata.org/prop/>
  PREFIX ps:       <http://www.wikidata.org/prop/statement/>
  PREFIX wikibase: <http://wikiba.se/ontology#>
  PREFIX schema:   <http://schema.org/>
  PREFIX rdfs:     <http://www.w3.org/2000/01/rdf-schema#>
  ```

- **No WDQS extension services.** `SERVICE wikibase:label`,
  `SERVICE mwapi`, and `wikibase:around`/`wikibase:box` do not exist.
  Get labels with plain triples, which QLever serves efficiently
  (unlike WDQS):

  ```sparql
  ?item rdfs:label ?label . FILTER(LANG(?label) = "en")
  ```

  Without the language filter you get every language's label.

- **Sitelink counts live on the sitelink node, not the entity.**
  QLever serves the RDF unmodified:

  ```sparql
  ?article schema:about ?item ; wikibase:sitelinks ?n .
  ```

  The direct `?item wikibase:sitelinks ?n` is a WDQS rewrite and
  matches nothing on QLever.

- **Integers** come back as `xsd:int`, never `xsd:integer`.
- **Coordinates** (`geo:wktLiteral` points) are stored at 6 decimal
  places of precision.
- Otherwise SPARQL 1.1 is fully supported: `FILTER NOT EXISTS`,
  `EXISTS`, `MINUS`, property paths, and subqueries all work.

## Extras WDQS does not have

- Combined SPARQL + full-text search over entity-linked English
  Wikipedia text (`PREFIX ql: <http://qlever.cs.uni-freiburg.de/builtin-functions/>`,
  predicates `ql:contains-entity` and `ql:contains-word`).
- English Wikipedia abstracts via `schema:description` with the article
  URL as subject.

## Query craft

- **Prefer aggregation over enumeration** — `COUNT(DISTINCT …)` with
  `GROUP BY` and `LIMIT`, not row dumps. Group by the QID only: items
  with multiple `P17`/`P1001`/`P31` values otherwise inflate rows.
- **Boolean coverage checks**: use `BIND(EXISTS { … } AS ?flag)`
  rather than `OPTIONAL` patterns you then have to coalesce.
- **Give queries room, then rewrite.** Match QLever's server timeout
  with `--max-time 600`; a shorter client abort produces a false
  "timeout" failure. A query that genuinely needs minutes is a query
  to narrow, not to wait out.
- **Fetch labels last.** Restrict to the final rows (`VALUES`, a
  subquery, or `LIMIT`) before joining `rdfs:label`; unanchored
  `OPTIONAL` label joins are the classic memory blow-up.
- **Never guess QIDs.** Anchor only on QIDs you have verified in this
  session — from a query result or a live REST read. A remembered or
  assumed QID that is wrong silently poisons every downstream query.
- **Anchor on exact classes or known QIDs.** Fully unanchored queries
  time out even on QLever, and broad `P31/P279*` sweeps scoped only by
  `P17`/`P1001` drown in companies, banks, and embassies. When a class
  path is needed, verify the class roots first: a class query that
  returns zero rows is a failed query, not evidence of absence — check
  the root QIDs and say so.
- **Label-based discovery hits disambiguation pages.** Searching items
  by label surfaces disambiguation pages, list articles, and generic
  occupations alongside real items. Confirm a candidate by its class
  and links before anchoring on it.
- **A failed or empty query is information about the query first.**
  QLever rejects some constructs WDQS tolerates (certain variable
  property paths, regex escaping). Simplify, split, or rewrite; when
  documenting research, keep both the failing and the working version
  rather than silently dropping the failure.
- **Entities**: inspect single interesting items via the REST API
  (below); never bulk-download entities.

## Live entity data

For the current state of one entity, GET it from the REST API:

```bash
curl -s https://www.wikidata.org/w/rest.php/wikibase/v1/entities/items/Q…
```

The REST API rate-limits: pace single-entity reads instead of bursting
them, and use QLever for anything bulk. Do not use REST reads to check
whether the mirror is fresh — it follows the change stream and is
seconds behind live. If a live entity looks "richer" than a query
result, the query's `SELECT` was narrower, not the mirror staler:
profile the item with a `VALUES`-anchored query instead. A throttled
response (429 or an HTML error page) is not evidence: back off, retry
once after a pause, and never save the error body as a result file.

The response is where statement GUIDs come from (see the
`propose-edits` skill): `patchItemStatement` and `deleteItemStatement`
edits address one statement by its `id` (`Q…$1B7C…`). Statements at
every rank — preferred, normal, and deprecated — are included.
