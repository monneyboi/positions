# Wikidata political-position quality: one-day improvement audit

**Audit date:** 2026-07-24  
**Data source:** live Wikidata Query Service (WDQS) and Wikidata API  
**Scope:** position items used as values of [`position held (P39)`](https://www.wikidata.org/wiki/Property:P39), with emphasis on political and public offices  
**Goal:** identify high-impact, low-risk work that an experienced programmer using AI agents could complete in one day

## Executive summary

The best use of one day is not a global attempt to fill missing dates or qualifiers. Wikidata's position data combines several modeling traditions, and many apparent omissions are legitimate. The strongest opportunities are narrow batches where existing graph structure supplies most of the answer.

Recommended order:

1. **Backfill jurisdictional context on 131 position items.** These positions lack both `country (P17)` and `applies to jurisdiction (P1001)`, but their `part of (P361)` legislative body already supplies both values. They are used in **6,436 truthy person–position links**. This is the safest structural batch.
2. **Reconcile `position holder (P1308)` with missing inverse P39 statements.** There are **390 person–office pairs across 164 directly typed public offices** where an office says that a person held it, but the person has no P39 statement for the office at any rank. The source data consists of 498 P1308 tenure statements, many with dates and some with references.
3. **Repair high-use gaps in the position hierarchy.** There are **2,540 directly typed public offices without a direct `subclass of (P279)`**, affecting **6,397 truthy links**. This is important for software that discovers political positions through ontology traversal, but parent selection requires human review.
4. **Add English descriptions and labels.** Among directly typed public offices in use, **6,286 lack an English description** and **1,234 lack an English label**. Descriptions alone affect **34,324 truthy links** and are a safe use of AI-assisted translation and templating.
5. **Investigate list items used as positions.** P39 points to **677 items typed as Wikimedia lists**, affecting **3,247 truthy links**. These are real defects but may require statement migration rather than a simple item edit.
6. **Use 14 malformed US House statements as a quick warm-up.** They contain at least one start date later than an end date. Several have multiple tenures merged into one statement and must be split rather than having dates swapped.

A productive day should combine one deterministic batch, one holder-reconciliation batch, and a small reviewed taxonomy or labeling batch.

---

## 1. Scope and methodology

### 1.1 What was counted

The main universe was obtained with:

```sparql
SELECT (COUNT(*) AS ?links)
       (COUNT(DISTINCT ?position) AS ?positions)
WHERE {
  ?person wdt:P39 ?position
}
```

Live result:

| Metric | Count |
|---|---:|
| Truthy direct P39 links | 1,608,359 |
| Distinct values used by P39 | 147,107 |

A `wdt:P39` result is a truthy RDF link, not necessarily one Wikidata statement. If a person held the same office in several separate tenures, the direct person–position triple is still only one link. Statement-level audits therefore use `p:P39`, `ps:P39`, qualifiers, and statement ranks instead.

### 1.2 High-precision public-office subset

For safer structural analysis, many queries were restricted to values directly typed:

```sparql
?position wdt:P31 wd:Q294414 .  # public office
```

This subset contains:

| Metric | Count |
|---|---:|
| Distinct used position items | 17,712 |
| Truthy P39 links | 132,817 |

This is **not the complete political-office universe**. Wikidata also models offices as instances of `position (Q4164871)`, `elective office (Q17279032)`, historical-position classes, term-specific roles, and other types. For example, several major parliamentary roles are not directly typed Q294414. The exact-Q294414 subset is useful because it is comparatively high precision, not because it is ontologically complete.

### 1.3 Modeling guidance used

The audit was evaluated against:

- [WikiProject every politician: Political data model](https://www.wikidata.org/wiki/Wikidata:WikiProject_every_politician/Political_data_model)
- [`position held (P39)` and its constraints](https://www.wikidata.org/wiki/Property:P39)
- [`position holder (P1308)` and its inverse constraint](https://www.wikidata.org/wiki/Property:P1308)

The political data model recommends the following for legislature-membership positions and cabinet-level offices:

- `instance of (P31): public office (Q294414)`
- `country (P17)`
- `applies to jurisdiction (P1001)`
- a suitable `subclass of (P279)`
- `part of (P361)` the relevant legislature, cabinet, or government

For P39 statements it recommends dates where known, separate statements for non-consecutive tenures, and context qualifiers such as legislative term, cabinet, district, and parliamentary group where applicable.

### 1.4 Important limitations

- WDQS is live and eventually consistent; counts will change.
- `P39` is not political-only. It also contains religious, academic, military, organizational, and other roles.
- Missing metadata is not automatically an error. Generic role classes such as “president” should not receive a single country or organization.
- Direct `P31 Q294414` is intentionally a narrow proxy.
- Counts of truthy links are not counts of tenure statements.
- This audit identifies edit candidates; it does not establish sources for every proposed claim.

---

## 2. Baseline metadata coverage

Across all 147,107 used P39 values, regardless of whether they are political:

| Position-item property | Used position values with property | Approx. coverage |
|---|---:|---:|
| `country (P17)` | 93,171 | 63.3% |
| `applies to jurisdiction (P1001)` | 116,841 | 79.4% |
| `part of (P361)` | 21,207 | 14.4% |
| `inception (P571)` | 13,798 | 9.4% |
| `dissolved, abolished or demolished date (P576)` | 5,279 | 3.6% |
| `position holder (P1308)` | 9,860 | 6.7% |

These figures are descriptive, not target completion rates. P361, lifecycle dates, and P1308 are not appropriate for every kind of position.

Within the directly typed public-office subset:

| Gap | Position items | Truthy P39 links affected |
|---|---:|---:|
| Missing P17 | 2,057 | 24,399 |
| Missing P1001 | 1,075 | 22,742 |
| Missing both P17 and P1001 | 440 | 16,805 |
| Missing P361 | 9,316 | 44,032 |
| Missing direct P279 | 2,540 | 6,397 |
| Missing English label | 1,234 | 3,418 |
| Missing English description | 6,286 | 34,324 |

The raw gaps are not all actionable. For example, generic `president (Q30461)` accounts for 6,268 links in the “missing both P17 and P1001” result, and generic `senator (Q15686806)` accounts for another 2,087. Adding one jurisdiction to such generic roles would be wrong. The deterministic 131-item subset below removes much of that ambiguity.

---

## 3. Priority 1: deterministic jurisdiction backfill

### 3.1 Finding

There are **131** used position items that:

- are directly typed `public office (Q294414)`;
- have `part of (P361)` a body;
- lack both P17 and P1001; and
- point to a body that already has both P17 and P1001.

They cover **6,436 truthy person–position links**.

Reproducible count query:

```sparql
SELECT (COUNT(DISTINCT ?position) AS ?positions)
       (COUNT(*) AS ?links)
WHERE {
  ?person wdt:P39 ?position .
  ?position wdt:P31 wd:Q294414 .

  FILTER NOT EXISTS { ?position wdt:P17 [] }
  FILTER NOT EXISTS { ?position wdt:P1001 [] }

  FILTER EXISTS {
    ?position wdt:P361 ?body .
    ?body wdt:P17 [];
          wdt:P1001 [] .
  }
}
```

Work-queue query:

```sparql
SELECT ?position ?positionLabel
       ?body ?bodyLabel
       ?country ?countryLabel
       ?jurisdiction ?jurisdictionLabel
       (COUNT(?person) AS ?links)
WHERE {
  ?person wdt:P39 ?position .
  ?position wdt:P31 wd:Q294414;
            wdt:P361 ?body .
  ?body wdt:P17 ?country;
        wdt:P1001 ?jurisdiction .

  FILTER NOT EXISTS { ?position wdt:P17 [] }
  FILTER NOT EXISTS { ?position wdt:P1001 [] }

  SERVICE wikibase:label {
    bd:serviceParam wikibase:language "en,[AUTO_LANGUAGE]" .
  }
}
GROUP BY ?position ?positionLabel
         ?body ?bodyLabel
         ?country ?countryLabel
         ?jurisdiction ?jurisdictionLabel
ORDER BY DESC(?links)
```

### 3.2 Largest visible cluster

The leading candidates are a coherent batch of Russian regional legislative roles:

| Position | Label | P39 links | Body-derived P17 | Body-derived P1001 |
|---|---|---:|---|---|
| [Q133268398](https://www.wikidata.org/wiki/Q133268398) | member of the People's Assembly of the Republic of Dagestan | 180 | Russia (Q159) | Dagestan (Q5118) |
| [Q133268352](https://www.wikidata.org/wiki/Q133268352) | member of the State Assembly of Bashkortostan | 153 | Russia | Bashkortostan (Q5710) |
| [Q133268339](https://www.wikidata.org/wiki/Q133268339) | Member of the Altai Krai Legislative Assembly | 146 | Russia | Altai Krai (Q5942) |
| [Q133268380](https://www.wikidata.org/wiki/Q133268380) | Member of the Legislative Assembly of Novosibirsk Oblast | 125 | Russia | Novosibirsk Oblast (Q5851) |
| [Q133268405](https://www.wikidata.org/wiki/Q133268405) | member of the Parliament of the Kabardino-Balkar Republic | 119 | Russia | Kabardino-Balkaria (Q5267) |
| [Q133268363](https://www.wikidata.org/wiki/Q133268363) | Member of the Legislative Assembly of Krasnodar Krai | 118 | Russia | Krasnodar Krai (Q3680) |
| [Q133268401](https://www.wikidata.org/wiki/Q133268401) | member of the People's Khural of the Republic of Buryatia | 116 | Russia | Buryatia (Q6809) |
| [Q133268384](https://www.wikidata.org/wiki/Q133268384) | member of the Legislative Assembly of Perm Krai | 115 | Russia | Perm Krai (Q5400) |
| [Q133268349](https://www.wikidata.org/wiki/Q133268349) | Member of the Duma of the Astrakhan Region | 114 | Russia | Astrakhan Oblast (Q3941) |
| [Q133268371](https://www.wikidata.org/wiki/Q133268371) | member of the Legislative Assembly of Kirov Region | 112 | Russia | Kirov Oblast (Q5387) |

### 3.3 Why this is low hanging fruit

- The item already identifies its legislature through P361.
- The legislature already carries machine-readable country and jurisdiction.
- The political data model explicitly expects P17 and P1001 on legislature-membership positions.
- The batch is coherent enough for deterministic candidate generation.
- Adding these properties improves disambiguation, country filtering, office matching, and downstream candidate ranking without changing holder statements.

### 3.4 Required safeguards

Do not mechanically copy values until checking:

1. The body has exactly one relevant P17 and P1001 for the office's valid period.
2. The body is the legislature or government to which the position belongs, not an unrelated organization.
3. Historical offices do not require a historical country rather than a present-day country.
4. The target position has no non-truthy or deprecated conflicting P17/P1001 statement.
5. A suitable external source can support the relationship. Wikidata itself is not a source.

A script should produce a CSV containing the position, body, candidate values, body statement IDs, existing claims at all ranks, labels, and source candidates. Human approval should precede QuickStatements or API submission.

---

## 4. Priority 2: reconcile P1308 with missing P39

### 4.1 Finding

`position holder (P1308)` is declared as the inverse of `position held (P39)`. In the directly typed public-office subset, there are:

- **164 offices** with at least one inverse gap;
- **390 distinct person–office pairs** where P1308 exists but no P39 statement exists at any rank;
- **498 non-deprecated P1308 statements** representing those pairs, because some people held the same office more than once;
- **352** source statements with P580;
- **289** with P582; and
- **125** with at least one reference.

Pair count query:

```sparql
SELECT (COUNT(DISTINCT ?pair) AS ?pairs)
       (COUNT(DISTINCT ?position) AS ?positions)
WHERE {
  ?position wdt:P31 wd:Q294414;
            wdt:P1308 ?person .

  FILTER NOT EXISTS {
    ?person p:P39/ps:P39 ?position
  }

  BIND(CONCAT(STR(?position), "|", STR(?person)) AS ?pair)
}
```

Statement-quality query:

```sparql
SELECT (COUNT(DISTINCT ?holderStatement) AS ?all)
       (COUNT(DISTINCT ?hasStart) AS ?withStart)
       (COUNT(DISTINCT ?hasEnd) AS ?withEnd)
       (COUNT(DISTINCT ?hasReference) AS ?withReference)
WHERE {
  ?position wdt:P31 wd:Q294414;
            p:P1308 ?holderStatement .

  ?holderStatement ps:P1308 ?person;
                   wikibase:rank ?rank .
  FILTER(?rank != wikibase:DeprecatedRank)

  FILTER NOT EXISTS {
    ?person p:P39/ps:P39 ?position
  }

  OPTIONAL {
    ?holderStatement pq:P580 [] .
    BIND(?holderStatement AS ?hasStart)
  }
  OPTIONAL {
    ?holderStatement pq:P582 [] .
    BIND(?holderStatement AS ?hasEnd)
  }
  OPTIONAL {
    ?holderStatement prov:wasDerivedFrom [] .
    BIND(?holderStatement AS ?hasReference)
  }
}
```

Detailed work queue:

```sparql
SELECT ?position ?positionLabel
       ?person ?personLabel
       ?holderStatement ?rank
       ?start ?end ?cabinet ?ordinal
WHERE {
  ?position wdt:P31 wd:Q294414;
            p:P1308 ?holderStatement .

  ?holderStatement ps:P1308 ?person;
                   wikibase:rank ?rank .
  FILTER(?rank != wikibase:DeprecatedRank)

  FILTER NOT EXISTS {
    ?person p:P39/ps:P39 ?position
  }

  OPTIONAL { ?holderStatement pq:P580 ?start }
  OPTIONAL { ?holderStatement pq:P582 ?end }
  OPTIONAL { ?holderStatement pq:P5054 ?cabinet }
  OPTIONAL { ?holderStatement pq:P1545 ?ordinal }

  SERVICE wikibase:label {
    bd:serviceParam wikibase:language "en,[AUTO_LANGUAGE]" .
  }
}
ORDER BY ?position ?person ?start
```

### 4.2 Highest-volume offices

| Office | Missing person–office pairs |
|---|---:|
| [Minister of Labour of Brazil (Q52334511)](https://www.wikidata.org/wiki/Q52334511) | 42 |
| [Minister for Homes (Q108617300)](https://www.wikidata.org/wiki/Q108617300) | 22 |
| [President of the Reichstag (Q1312424)](https://www.wikidata.org/wiki/Q1312424) | 16 |
| [Chief Justice of the North Dakota Supreme Court (Q81589384)](https://www.wikidata.org/wiki/Q81589384) | 14 |
| [Minister for Hospitality and Racing (Q111139875)](https://www.wikidata.org/wiki/Q111139875) | 12 |
| [Minister for Agriculture (Q6865936)](https://www.wikidata.org/wiki/Q6865936) | 11 |
| [President of the Chamber of Deputies (Q51625452)](https://www.wikidata.org/wiki/Q51625452) | 9 |
| [Director-General for Public Works (Q51955121)](https://www.wikidata.org/wiki/Q51955121) | 9 |
| [Governor of the State Bank of Vietnam (Q10826610)](https://www.wikidata.org/wiki/Q10826610) | 7 |

The Brazilian minister item has 62 P1308 statements in total. Example statements carry dates, cabinet membership, and series ordinals. The Australian `Minister for Homes` statements commonly contain dates, cabinet qualifiers, and references. These are particularly promising coherent migrations.

### 4.3 Correct transformation

For each valid P1308 tenure:

- subject becomes the person;
- property becomes P39;
- value becomes the position;
- copy qualifiers that are allowed and retain the same meaning in the inverse orientation, including P580, P582, P5054, P1545, and suitable succession qualifiers;
- copy references when they support the inverse statement equally;
- preserve separate non-consecutive tenures as separate P39 statements;
- do not create a duplicate if an equivalent P39 statement appears between extraction and submission.

### 4.4 Risks

- Several P1308 statements for one pair may be legitimate repeated tenures, exact duplicates, or overlapping errors.
- A reference may support the office-centric claim but need checking before reuse.
- Preferred-rank P1308 statements can suppress normal-rank values in `wdt:` queries, which is why duplicate detection must inspect all P39 ranks.
- Do not infer missing dates merely to make the new statement look complete.
- Consider whether the office's P1308 list itself is current and sourced before propagating it.

This task directly improves holder coverage and is therefore highly relevant to a political-position-holder project.

---

## 5. Priority 3: missing position hierarchy

### 5.1 Finding

Among used values directly typed `public office (Q294414)`:

- **2,540** lack a direct P279 statement;
- these items are used by **6,397 truthy P39 links**.

Query:

```sparql
SELECT ?position ?positionLabel
       (COUNT(?person) AS ?links)
WHERE {
  ?person wdt:P39 ?position .
  ?position wdt:P31 wd:Q294414 .
  FILTER NOT EXISTS { ?position wdt:P279 [] }

  SERVICE wikibase:label {
    bd:serviceParam wikibase:language "en,[AUTO_LANGUAGE]" .
  }
}
GROUP BY ?position ?positionLabel
ORDER BY DESC(?links)
```

### 5.2 High-use examples

| Position | Links | Comment |
|---|---:|---|
| [Assistant Whip (Q115325171)](https://www.wikidata.org/wiki/Q115325171) | 231 | UK government office; likely parent can be identified from sibling whip offices |
| [Director General (Q112187535)](https://www.wikidata.org/wiki/Q112187535) | 191 | Label is generic; jurisdiction and organization must drive classification |
| [Lord Commissioner of the Treasury (Q3259412)](https://www.wikidata.org/wiki/Q3259412) | 158 | Established UK political office |
| [Lord-in-waiting (Q5212367)](https://www.wikidata.org/wiki/Q5212367) | 141 | Established UK government/royal-household office |
| [Treasurer of New South Wales (Q7836754)](https://www.wikidata.org/wiki/Q7836754) | 50 | Clear jurisdiction-specific treasury office |
| [Vice-Chamberlain of the Household (Q426461)](https://www.wikidata.org/wiki/Q426461) | 45 | Requires careful political versus royal-household classification |
| [Treasurer of the United States (Q369142)](https://www.wikidata.org/wiki/Q369142) | 45 | Clear country-specific office |

The queue also exposes malformed items. For example, several Wikimedia lists are additionally typed as public offices and therefore appear as missing-P279 candidates. A missing P279 must not be “fixed” before checking whether the item's P31 is itself wrong.

### 5.3 Why P279 matters

P279 is central to:

- discovering all offices beneath concepts such as minister, legislator, mayor, judge, or head of government;
- matching extracted free-text positions to jurisdiction-specific Wikidata items;
- preventing generic roles from being substituted for specific offices;
- country- and office-family analytics; and
- constraint checking of P39 values.

For software that imports position descendants, a missing parent can make an otherwise valid office unreachable.

### 5.4 Agent-assisted review design

For each candidate, retrieve:

1. all labels and descriptions;
2. P17, P1001, P361, P2389, P108, P571, and P576;
3. sibling offices attached to the same body or jurisdiction;
4. the P279 paths of those siblings;
5. Wikipedia introductions and official government pages;
6. proposed parents with confidence and rationale.

The agent should produce candidates, not edits. Human review should reject:

- parents inferred solely from similar words;
- a generic parent that is actually an occupation rather than a position class;
- class/instance mixing;
- classification based on a mistranslated label; and
- a parent that only applied during one historical period.

A realistic one-day goal is the top 50–100 reviewed items, not all 2,540.

---

## 6. Priority 4: English labels and descriptions

### 6.1 Finding

Among used position items directly typed public office:

| Gap | Positions | Truthy P39 links affected |
|---|---:|---:|
| No English label | 1,234 | 3,418 |
| No English description | 6,286 | 34,324 |

Count query for labels:

```sparql
SELECT (COUNT(DISTINCT ?position) AS ?positions)
       (COUNT(*) AS ?links)
WHERE {
  ?person wdt:P39 ?position .
  ?position wdt:P31 wd:Q294414 .
  FILTER NOT EXISTS {
    ?position rdfs:label ?label .
    FILTER(LANG(?label) = "en")
  }
}
```

Count query for descriptions:

```sparql
SELECT (COUNT(DISTINCT ?position) AS ?positions)
       (COUNT(*) AS ?links)
WHERE {
  ?person wdt:P39 ?position .
  ?position wdt:P31 wd:Q294414 .
  FILTER NOT EXISTS {
    ?position schema:description ?description .
    FILTER(LANG(?description) = "en")
  }
}
```

### 6.2 Examples lacking English labels

| Position | P39 links | Existing label context |
|---|---:|---|
| [Q140359954](https://www.wikidata.org/wiki/Q140359954) | 191 | German: *Rektor der Universität Rostock* |
| [Q62973223](https://www.wikidata.org/wiki/Q62973223) | 79 | Italian/French labels describe a deputy of the Roman Republic's constituent assembly |
| [Q108424705](https://www.wikidata.org/wiki/Q108424705) | 55 | Swedish: councillor/judge in Skänninge town court |
| [Q63247831](https://www.wikidata.org/wiki/Q63247831) | 30 | Spanish/Catalan: provincial deputy of Alicante |
| [Q140631891](https://www.wikidata.org/wiki/Q140631891) | 27 | Swedish: mayor of Stockholm |
| [Q125813782](https://www.wikidata.org/wiki/Q125813782) | 27 | Swedish: mayor of Linköping |

Not every directly typed public office is political; the Rostock rector is an example. A political-only labeling batch should additionally filter by parent class, jurisdiction, or relevant body.

### 6.3 Safe automation strategy

Labels and descriptions are well suited to AI assistance because the edit can be generated from existing structured facts:

- use the best native-language label and aliases;
- use P1001 for the place or jurisdiction;
- use P361/P2389 for the legislature, cabinet, court, municipality, or ministry;
- use P279 to identify the role family;
- compare against sibling items' English wording;
- preserve official capitalization only where Wikidata style calls for it.

Suggested description patterns:

- `member of the legislative body of <jurisdiction>`
- `cabinet-level ministerial office in <jurisdiction>`
- `municipal political office in <place>`
- `historical public office in <state>, <years>`

Do not insert facts in a description that are not supported by claims or reliable source text. Run duplicate-label checks within the same jurisdiction and office family.

---

## 7. Priority 5: list items used as P39 values

### 7.1 Finding

There are **677 distinct P39 values**, used in **3,247 truthy links**, that are typed as one of:

- `Wikimedia list article (Q13406463)`; or
- `Wikimedia list of persons (Q19692233)`.

Query:

```sparql
SELECT ?position ?positionLabel
       ?listClass ?listClassLabel
       (COUNT(?person) AS ?links)
WHERE {
  ?person wdt:P39 ?position .
  VALUES ?listClass { wd:Q13406463 wd:Q19692233 }
  ?position wdt:P31 ?listClass .

  SERVICE wikibase:label {
    bd:serviceParam wikibase:language "en,[AUTO_LANGUAGE]" .
  }
}
GROUP BY ?position ?positionLabel ?listClass ?listClassLabel
ORDER BY DESC(?links)
```

Breakdown:

| List class | Distinct used values | Truthy links |
|---|---:|---:|
| Wikimedia list article (Q13406463) | 665 | 2,366 |
| Wikimedia list of persons (Q19692233) | 13 | 881 |

The class totals overlap by one item, hence 677 distinct values overall rather than 678.

### 7.2 Prominent cases

| Item | Links | Issue |
|---|---:|---|
| [Lord Warden of the Cinque Ports (Q1809853)](https://www.wikidata.org/wiki/Q1809853) | 103 | Real office also typed as a Wikimedia list; likely an erroneous P31 on the item |
| [Q108742737](https://www.wikidata.org/wiki/Q108742737) | 92 | list of members of the Supreme Soviet of the Byelorussian SSR, 1962–1966, used as a position |
| [Q108660082](https://www.wikidata.org/wiki/Q108660082) | 89 | corresponding 1955–1959 member list used as a position |
| [Q108743131](https://www.wikidata.org/wiki/Q108743131) | 88 | corresponding 1971–1974 list, additionally typed public office |
| [Q108626601](https://www.wikidata.org/wiki/Q108626601) | 86 | corresponding 1951–1954 list used as a position |
| [Q108742876](https://www.wikidata.org/wiki/Q108742876) | 84 | corresponding 1967–1970 list used as a position |
| [list of members of the 3rd Lok Sabha (Q48723974)](https://www.wikidata.org/wiki/Q48723974) | 69 | list article used as term-specific office |

### 7.3 Two distinct remediation patterns

#### Pattern A: the item is an office with an erroneous list type

Example: Lord Warden of the Cinque Ports. Review whether the list-type P31 should be removed while retaining its position/public-office typing.

#### Pattern B: the P39 value is genuinely a list article

For list articles representing a legislative term, holders should generally use:

- the non-term-specific membership position as the P39 value; and
- the relevant term as a `legislative term (P2937)` qualifier.

The political data model permits existing term-specific membership-position items in some country models, but says they must subclass the general membership position and the person's P39 statement must still carry P2937. A Wikimedia list article is not itself a position.

### 7.4 Why this should not be the first mass edit

Migration may require:

- identifying or creating the correct legislative-term item;
- identifying the correct general membership position;
- replacing hundreds of P39 values;
- preserving dates, districts, groups, references, and ranks;
- removing an erroneous P31 from some items but not others; and
- discussing a country-specific modeling change with the relevant WikiProject.

This is an excellent audit and proposal target, but a dangerous blind QuickStatements task.

---

## 8. Secondary target: P39 statement quality

Position-item quality is only half the problem. A well-modeled office still produces poor holder tracking when P39 statements are malformed or lack evidence.

### 8.1 US House impossible intervals

For `United States representative (Q13218630)`, there are **14 distinct statement nodes** with at least one start date later than an end date. The raw query produces 18 start/end combinations because some malformed statements contain multiple start or end qualifiers.

```sparql
SELECT DISTINCT ?person ?statement
WHERE {
  ?person p:P39 ?statement .
  ?statement ps:P39 wd:Q13218630;
             pq:P580 ?start;
             pq:P582 ?end .
  FILTER(?start > ?end)
}
```

These examples usually show several tenures accidentally merged into one statement. Correct repair is typically:

1. inspect all start dates, end dates, terms, districts, groups, and references;
2. identify actual service intervals from an authoritative source;
3. create one statement per non-consecutive tenure or changing context; and
4. remove or replace the malformed merged statement.

Simply swapping the start and end dates would often create another incorrect statement.

### 8.2 US Senate as a bounded completeness audit

`United States senator (Q4416090)` is a comparatively mature and structured corpus. A live statement-level query found approximately:

| Metric | Statements missing field |
|---|---:|
| Start time | 13 |
| End time | 117 |
| Legislative term | 23 |
| Electoral district | 18 |
| Parliamentary group | 549 |
| Any reference | 74 |

Missing end time includes incumbents and is therefore not automatically an error. Missing parliamentary group may also require modeling judgment. The small missing-start, missing-term, missing-district, and unsourced queues are suitable for comparison against authoritative Senate sources.

Reusable coverage query:

```sparql
SELECT (COUNT(DISTINCT ?statement) AS ?all)
       (COUNT(DISTINCT ?hasStart) AS ?withStart)
       (COUNT(DISTINCT ?hasEnd) AS ?withEnd)
       (COUNT(DISTINCT ?hasTerm) AS ?withTerm)
       (COUNT(DISTINCT ?hasDistrict) AS ?withDistrict)
       (COUNT(DISTINCT ?hasGroup) AS ?withGroup)
       (COUNT(DISTINCT ?hasReference) AS ?withReference)
WHERE {
  ?person p:P39 ?statement .
  ?statement ps:P39 wd:Q4416090 .

  OPTIONAL { ?statement pq:P580 [] . BIND(?statement AS ?hasStart) }
  OPTIONAL { ?statement pq:P582 [] . BIND(?statement AS ?hasEnd) }
  OPTIONAL { ?statement pq:P2937 [] . BIND(?statement AS ?hasTerm) }
  OPTIONAL { ?statement pq:P768 [] . BIND(?statement AS ?hasDistrict) }
  OPTIONAL { ?statement pq:P4100 [] . BIND(?statement AS ?hasGroup) }
  OPTIONAL { ?statement prov:wasDerivedFrom [] . BIND(?statement AS ?hasReference) }
}
```

### 8.3 What not to bulk-fill

Do not automatically add:

- an end date to every statement missing one;
- a legislative term where the legislature is not term-based;
- a parliamentary group from the person's general party membership;
- an electoral district where no district applies;
- a single start/end pair to a statement with multiple mandates; or
- references that mention the person but do not support the specific tenure.

---

## 9. Recommended one-day execution plan

### Phase 0: preparation — 30 minutes

- Save WDQS outputs with timestamps.
- Fetch full entities and all statement ranks through the Wikidata API.
- Create a local SQLite or DuckDB review database.
- Record candidate reason, source values, proposed edits, confidence, and review state.
- Announce any planned large or systematic batch in the relevant WikiProject or project chat and follow Wikidata mass-edit/bot policy.

### Phase 1: quick integrity repairs — 30–60 minutes

Review the 14 malformed US House statement nodes. Fix only cases where an authoritative service record clearly determines the proper statement split.

This validates the edit and review pipeline on a small set before making larger changes.

### Phase 2: jurisdiction batch — 2–3 hours

- Generate the 131-position queue.
- Restrict the first submission to the coherent Russian regional-legislature cluster or another single jurisdiction family.
- Check cardinality and historical-state exceptions.
- Attach external references where available.
- Generate QuickStatements or API edits only after review.
- Re-run the query and inspect a random sample of edited items.

Expected result: up to 262 structural claims improving 6,436 existing holder links.

### Phase 3: inverse-holder reconciliation — 2–3 hours

Choose one or two coherent office families, for example:

- Minister of Labour of Brazil;
- Australian ministerial portfolios; or
- President of the Reichstag.

For each P1308 statement:

- compare all existing P39 statements at all ranks;
- split repeated tenures correctly;
- transfer allowed qualifiers and references;
- preserve precision and calendar model for dates;
- queue unsourced or conflicting cases for manual research.

A realistic target is 50–150 high-confidence P39 statements rather than all 498 source statements.

### Phase 4: taxonomy or language — 1–2 hours

Choose one:

- review the top 25–50 missing-P279 offices; or
- add English labels/descriptions to a jurisdictionally coherent set.

Taxonomy edits have higher structural value but greater ontology risk. Language edits are safer and faster.

### Phase 5: validation and reporting — 30 minutes

- Re-run every candidate query.
- Check that edited items no longer appear for the intended reason.
- Check for new constraint violations.
- Inspect at least 10% of edits manually.
- Save item IDs, revisions, sources, rejected candidates, and reasons.
- Publish or retain a machine-readable edit report for rollback.

---

## 10. Suggested automation architecture

### 10.1 Deterministic extractor

Use SPARQL only to identify candidates. Fetch final entity JSON from the Wikidata API immediately before review and again before submission.

Recommended local record:

```text
candidate_id
candidate_type
position_qid
person_qid
source_statement_id
existing_claims_json
proposed_claims_json
source_urls
confidence
agent_rationale
human_decision
submission_revision_id
```

### 10.2 Rules engine

Hard rules should reject candidates when:

- a target claim already exists at any rank;
- country or jurisdiction candidates are multi-valued without temporal disambiguation;
- P580 is later than P582;
- a copied qualifier is not permitted on P39;
- two proposed tenures overlap incompatibly;
- the position is a Wikimedia list, category, disambiguation page, or another invalid P39 value;
- the person is not plausibly a person or allowed P39 subject type;
- the source statement is deprecated; or
- no source supports the factual addition.

### 10.3 Appropriate AI-agent tasks

Good uses:

- translate labels;
- draft concise descriptions from structured context;
- retrieve likely official sources;
- rank candidate P279 parents;
- identify sibling position patterns;
- summarize conflicts for human review;
- classify list-item remediation patterns; and
- produce review diffs.

Bad uses:

- invent tenure dates;
- choose a jurisdiction from a name alone;
- treat party membership as parliamentary group without term evidence;
- select a parent solely by semantic embedding similarity;
- create statements without source verification; or
- submit unattended edits based only on model confidence.

### 10.4 Submission strategy

- Prefer small, coherent batches with meaningful edit summaries.
- Include the source URL or cited-item/reference details where appropriate.
- Use optimistic concurrency or compare entity revision IDs before editing.
- Stop the batch if the rejection/error rate exceeds a chosen threshold.
- Keep exact rollback data.

---

## 11. Prioritization matrix

| Task | Impact | Confidence | Automation potential | Modeling risk | One-day recommendation |
|---|---|---|---|---|---|
| Copy reviewed P17/P1001 from P361 body | High | High | High | Low–medium | **Do first** |
| Reconcile P1308 into missing P39 | High for holder coverage | Medium–high | Medium–high | Medium | **Do one office family** |
| Add missing P279 | High for taxonomy/discovery | Medium | Medium | Medium–high | Review top 25–100 |
| Add English descriptions | Medium–high | High | High | Low | Good fallback task |
| Add English labels | Medium | High | High | Low | Good filler task |
| Repair list-valued P39 | High where affected | High that a defect exists | Medium | High migration risk | Investigate/propose first |
| Fill global missing dates | Superficially high | Low | Low | High | Avoid |
| Fill P361 globally | Superficially high | Low | Low–medium | High | Avoid |
| Add P1308 to every P39 office | Low/duplicative | Low | High | High maintenance burden | Avoid |

---

## 12. Conclusion

The most valuable low-hanging fruit is **not adding more loosely sourced holder dates**. It is making existing position entities easier to identify and traverse, and reconciling information that Wikidata already stores on the inverse side of the holder relationship.

For a project whose extraction and matching quality depends on position entities, the best first batch is the 131 jurisdiction-inheritable offices. It is small, coherent, structurally justified, and improves 6,436 existing holder links. The best direct holder-completeness task is the 390 missing P39 inverse pairs, handled one office family at a time while preserving tenure boundaries, qualifiers, and references. A reviewed P279 batch then improves ontology traversal, while labels and descriptions provide a safe way to use AI agents at scale.

The key principle is to let code produce exhaustive queues and consistency checks, let AI agents gather context and rank options, and reserve ontology decisions and factual submission for human review.
