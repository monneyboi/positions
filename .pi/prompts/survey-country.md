---
description: Survey how a country's political system is modeled in Wikidata, into the research cache
argument-hint: "<country QID>"
---
You are doing **research only** for the `positions` project (a human-in-the-loop
queue for improving political position items on Wikidata). Your job: map how the
political positions of the country item **$1** are currently modeled in
Wikidata. The results feed two consumers: the derivation of a general
positions model across countries, and a per-country diff against that model
that produces edit hypotheses. Do NOT edit Wikidata, do NOT run
`positions queue`, do NOT touch any SQLite database, and do NOT write
anything outside your output directory.

Scope is the **positions side**: office items, the institutions they belong
to, jurisdictions, lifecycle. Politicians and the quality of their P39
statements are poliloom's domain — out of scope here, except as a
diagnostic for which offices exist and how they are used.

First read these two project skills completely — the model skill carries
the **country spine** (the slots you are filling) and the known false
positives; the querying skill carries the endpoint and query craft:

- .pi/skills/wikidata-querying/SKILL.md
- .pi/skills/wikidata-political-model/SKILL.md

Output directory: `cache/countries/<qid>/` where `<qid>` is $1 lowercased
(e.g. Q183 → `cache/countries/q183/`). Create it fresh: if it already exists,
remove its old contents first — this is a rebuild, not an append.

## Method

Work through the country spine slot by slot: verify the country item itself,
then its constitutional pointers (P194/P1313/P1906), the legislature and
chambers, the membership offices, the head-of-state/government offices, the
cabinet/government, and then other offices with significant holders tied to
the country via P17/P1001. Subnational first level: aggregate only, never
enumerate. Then check consistency across what you found: jurisdiction
asymmetry (offices with P17 but no P1001 or vice versa), lifecycle coverage
(P571/P576, succession chains, regime conflation), and P39 contamination
(values that are disambiguation pages, organizations, terms, list articles,
or cabinets rather than offices — each signals a missing or mis-modeled
position item).

As an input, not a source of truth: fetch
`Wikidata:WikiProject_every_politician/<Country>` and
`Wikidata:WikiProject_Heads_of_state_and_government/<Country>` if they
exist. Harvest their named QIDs (head offices, legislature, membership
items) as hypotheses, verify each against live state, and note staleness —
the pages are unevenly maintained.

Save every query as `NN-name.sparql` and its raw JSON response as
`NN-name.json`, numbered in run order — these are the evidence cache. All
counts are QLever mirror snapshots; say so. Inspect single interesting
entities with the REST API when needed, but never bulk-download. Failed
queries are documented in the README, not silently dropped.

## Deliverables

**`spine.json`** — the machine-readable result, one entry per spine slot:

```json
{
  "country": {"qid": "Q183", "label": "Germany"},
  "slots": {
    "headOfStateOffice": {"qid": "Q…", "status": "conformant"},
    "legislature": {"qid": "Q…", "status": "divergent", "note": "…"},
    "membershipOffice:Bundestag": {"qid": null, "status": "missing-item"}
  }
}
```

Status vocabulary: `conformant` / `divergent` / `missing-link` /
`missing-item`. Add slots beyond the skill's list when the country has
them (subnational, courts); mark slots that don't constitutionally apply
as `"status": "not-applicable"` with a note.

**`README.md`** — the human-readable report:

1. **Spine table** — the slots with QIDs and status (mirror of spine.json).
2. **Divergences** — established national practice that deviates from the
   general model, with evidence. A divergence is a finding to register,
   not an error.
3. **Anomalies and gaps** — each referencing the query file that surfaces
   it.
4. **Candidate edit opportunities** — 3–10, phrased as hypotheses for
   human verification, never as verified proposals.
5. **Surprises and failed queries** — including queries that returned
   nothing or had to be rewritten, and why.

When done, report back a concise summary of your main findings.
