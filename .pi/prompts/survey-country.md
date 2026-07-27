---
description: Survey how a country's political system is modeled in Wikidata, into the research cache
argument-hint: "<country QID>"
---
Research how the political positions of the country **$1** are currently
modeled in Wikidata, and how much of them there is. This is a
descriptive census: record what exists, how it is typed and linked, and
how many holders and statements it has. Do not judge conformity,
diagnose gaps, or propose edits — later cross-country analysis does
that; this survey is its fact base.

Scope is the positions side: office items (the values of P39), the
institutions they belong to, their jurisdictions, their lifecycle.
Politicians and their P39 statements are out of scope, except as
evidence of which offices exist and how they are used.

First read these two project skills — the model skill is your map of
the structures a country's political data typically consists of (what to
look for, not a checklist to grade); the querying skill carries the
endpoint and query craft:

- .pi/skills/wikidata-political-model/SKILL.md
- .pi/skills/wikidata-querying/SKILL.md

Hard boundaries: no Wikidata edits, no `positions queue`, no SQLite
databases, no writes outside the output directory (scratch work goes in
`/tmp`, never in the project tree).

Output directory: `cache/countries/<qid>/` where `<qid>` is $1
lowercased (e.g. Q183 → `cache/countries/q183/`). Rebuild it fresh:
remove old contents first.

## Sources

Start from the country item itself: query its label and constitutional
pointers (P1906/P1313/P194), and title the report with the verified
label — never assume which country the QID is. Then follow the graph
outward: legislature and chambers, membership offices,
head-of-state/government offices, cabinet/government, courts and other
offices with significant holders, first-level subnational offices in
aggregate (never enumerate).

Fetch the country's WikiProject pages as leads — named QIDs are
hypotheses to verify against the graph, never ground truth; the pages
are unevenly maintained. Page titles are not predictable from the
country name (the US page is `United States of America`, Iran's is
lowercase `iran`), and most countries have no page at all — so look
the country up in `.pi/skills/wikidata-political-model/wikiproject-pages.txt`,
the snapshot index of all country pages, and fetch exactly what is listed there: the Every
Politician page, its talk page if one is listed (`Wikidata_talk:...`
— discussion is evidence of unresolved practice), and the Heads of
state and government page if one is listed. A country absent from the
index is a finding to note, not a title to probe for.

Fetch each page with the MediaWiki API and save the raw JSON:

```bash
curl -sG 'https://www.wikidata.org/w/api.php' \
  --data-urlencode action=parse \
  --data-urlencode 'page=Wikidata:WikiProject_every_politician/<Country>' \
  --data-urlencode prop=wikitext --data-urlencode format=json \
  -o 00-wikiproject-every-politician.json
```

## Evidence discipline

Save every query as `NN-name.sparql` and its raw JSON response as
`NN-name.json`, numbered in run order; before writing the report, check
that every `.sparql` has its `.json`. All counts are QLever mirror
snapshots; say so in the report. The mirror is the evidence basis —
profile specific items with `VALUES`-anchored SPARQL queries, not REST
entity reads. Keep failed, empty, and rewritten queries in the numbered
sequence — they are evidence too — but never save throttled or error
response bodies as result files; record the failure in the query log.

## Deliverable

`README.md` in the output directory — a factual report:

1. **Overview** — headline numbers: offices found, total holders,
   institutions covered.
2. **Structure inventory** — what is actually modeled: constitutional
   pointers, legislature and chambers, membership offices, head offices,
   cabinet/government, courts, other significant offices, subnational
   aggregate. QIDs, types, and links for each; where a typical structure
   has no item, record the absence as an observation.
3. **Coverage in numbers** — holder counts per office; how many offices
   carry P17, P1001, both, or neither; lifecycle facts (P571/P576,
   succession links) present or absent; P39 values that are not offices
   (terms, cabinets, list articles, disambiguation pages), with counts.
4. **Modeling patterns** — country-specific modeling choices you
   observed, stated neutrally, each pointing at the query file that
   shows it.
5. **Query log** — failed, empty, and rewritten queries, and why.

When done, report back a concise summary of your main findings.
