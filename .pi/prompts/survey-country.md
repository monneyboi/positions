---
description: Survey how a country's political system is modeled in Wikidata, into the research cache
argument-hint: "<country QID>"
---
You are doing **research only** for the `positions` project (a human-in-the-loop
queue for improving political position items on Wikidata). Your job: map how the
political system of the country item **$1** is currently modeled in Wikidata, so
the team can reason about the model and later derive edit proposals. Do NOT edit
Wikidata, do NOT run `positions queue`, do NOT touch any SQLite database, and do
NOT write anything outside your output directory.

First read these two project skills completely — they carry the querying
conventions and the modeling vocabulary:

- .pi/skills/wikidata-querying/SKILL.md (QLever endpoint, required prefix block, pitfalls vs WDQS)
- .pi/skills/wikidata-political-model/SKILL.md (jurisdiction / institution / office / officeholder separation, lifecycle properties)

Output directory: `cache/countries/<qid>/` where `<qid>` is $1 lowercased
(e.g. Q183 → `cache/countries/q183/`). Create it fresh: if it already exists,
remove its old contents first — this is a rebuild, not an append.

## Method

Save every query as `NN-name.sparql` and its raw JSON response as `NN-name.json`
(curl against the QLever mirror per the querying skill). Number sequentially in
the order you run them. Work through this battery — adapt and extend when
results look odd, and drill down with follow-up queries:

1. **Baseline.** Verify the item: English label, all P31 values, P35 (head of
   state), P6 (head of government). Use the verified label as the country name
   throughout your README.
2. **Institutions.** Legislatures, chambers, cabinets/governments, courts,
   ministries tied to the country via P17 or P1001. Anchor on exact classes or
   known QIDs. Do NOT run broad `P31/P279*` sweeps scoped only by P17/P1001 —
   they drown in companies, banks, and embassies; every past survey rediscovered
   this.
3. **Offices.** Position items used as P39 values, tied to the country via
   P17/P1001 on the position item, aggregated with holder counts
   (`COUNT(DISTINCT ?person)`). Group by QID only — items with multiple
   P17/P1001/P31 values otherwise inflate rows.
4. **Office→body links.** Which of those offices have P361 (part of) / P2389 /
   P2388 links to an institution, and which high-holder ones have none.
5. **Officeholders.** Sample current-looking holders: P39 statements with P580
   and no P582. "Current" means no end qualifier, not verified incumbency.
6. **Subnational.** First-level subdivisions via P150 of $1 (check whether P150
   points to real subdivision items or to a list article!), then their offices
   and holders — aggregate only, never enumerate exhaustively.
7. **Jurisdiction asymmetry** (the workhorse query): positions with P17 = $1
   but no P1001, or vice versa, ranked by holders — using
   `BIND(EXISTS {...} AS ...)` flags, not OPTIONAL.
8. **P39 contamination.** P39 values that are Wikimedia disambiguation pages,
   organizations, legislative terms, list articles, or cabinets rather than
   offices. Get the class roots right; a class query that returns zero rows is
   a failed query, not evidence of absence — say so in the README.
9. **Lifecycle / temporal layer.** Coverage of P571/P576 on the country's
   offices; offices whose holders all have end dates but which lack P576;
   succession chains (P1365/P1366) where offices were abolished and replaced;
   regime-conflation (one office item with P17 values from mutually exclusive
   historical states).

## Known false-positive classes — do not propose edits for these blindly

- **Religious offices** (bishops etc.): P17 often denotes location, not
  governing jurisdiction.
- **Diplomatic offices** (ambassadors to the country): P17 denotes the country
  of accreditation.
- **Generic occupations** (mayor, judge, professor, president): must never
  receive country scope, however many holders they have.
- **Professional associations and companies**: P17 = country of incorporation
  or membership, not a political office.

## Query craft

- Declare every prefix yourself (see the querying skill's standard block).
- Prefer aggregation over enumeration; use LIMIT; be kind to QLever.
- QLever rejects some constructs WDQS tolerates (e.g. certain variable property
  paths, regex escaping). When a query fails, fix it and keep both versions —
  failed queries are documented in the README, not silently dropped.
- Inspect single interesting entities with wbgetentities when needed, but do
  not bulk-download entities.

## Deliverable contract

`README.md` in your output directory, with these sections:

1. **Baseline and overall model** — how the system is modeled
   (institutions → offices → holders), with QIDs and counts.
2. **Patterns and consistency** — which modeling patterns hold and which don't.
3. **Anomalies and gaps** — each referencing the query file that surfaces it.
4. **Candidate edit opportunities** — 3–10, phrased as hypotheses for human
   verification, never as verified proposals.
5. **Surprises and failed queries** — including queries that returned nothing
   or had to be rewritten, and why.

All counts are QLever mirror snapshots — say so. Never accept or submit any
edit. When done, report back a concise summary of your main findings.
