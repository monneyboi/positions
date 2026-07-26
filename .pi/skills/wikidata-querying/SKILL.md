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
- **Authoritative live state** → the MediaWiki API on
  `https://www.wikidata.org/w/api.php`. Always verify against this
  before queueing a proposal; it is also the only thing the submission
  path trusts.

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

## Live entity data

For the current state of one entity use `wbgetentities`:

```text
https://www.wikidata.org/w/api.php?action=wbgetentities&ids=Q…&props=info|labels|claims&format=json&formatversion=2
```

`formatversion=2` returns `entities` as a QID-keyed map. The claims
include all ranks — when checking whether a statement already exists,
inspect preferred, normal, **and deprecated** statements.
