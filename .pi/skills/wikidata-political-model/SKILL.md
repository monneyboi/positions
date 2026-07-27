---
name: wikidata-political-model
description: How political offices (P39 values), the institutions they belong to, territorial jurisdictions, and lifecycle are modeled on Wikidata — including the per-country "spine" of expected position items. Use when surveying a country's political data or judging edits to position items, legislatures, cabinets, ministries, or P17/P1001 statements. Politicians and their P39 statements are poliloom's domain, not this project's.
---

# Modeling political positions on Wikidata

## 1. Scope

This project models **positions**: office items (the values of
`position held (P39)`), the institutions they belong to, their
territorial jurisdiction, and their lifecycle. Politicians and their
P39 statements are [poliloom](https://github.com/opensanctions/poliloom)'s
domain; here P39 matters only as a diagnostic — the values people point
at reveal which offices exist and which are mis-modeled — and as a
constraint: edits to offices must not break the person links that rely
on them.

Coverage ambition is **every level of government** in every country —
national institutions, first-level subdivisions, municipalities, and
special-purpose bodies (water boards and similar functional
authorities) — each with its institutions and offices.

There is no single immutable Wikidata schema for political data. The
closest cross-country prescriptions are the WikiProject models listed
under Sources — all works in progress. Order of authority:

1. the property definitions themselves;
2. the topic WikiProject models (every politician, Parliaments, Heads
   of state and government, Govdirectory);
3. property constraints, as quality-control hints with valid exceptions;
4. established country-specific practice, where the general model
   permits alternatives;
5. talk-page discussions — evidence of unresolved questions, never
   settled guidance.

## 2. The central rule: keep four things separate

1. **territorial jurisdiction** — a country, state, province,
   municipality;
2. **institution** — a legislature, chamber, government, cabinet,
   ministry, agency;
3. **office** — the position item: member of a particular chamber, a
   particular ministerial portfolio, mayor of a particular city;
4. **officeholder** — the person.

A fifth object, a **legislative term or individual cabinet**, is a
time-bounded episode: not the enduring institution, not an office.

Most bad political data comes from collapsing these: a legislature,
cabinet, term, list article, or generic occupation used as a person's
P39 value. The simplified graph:

```text
territory ── P194 ──> legislature
territory ── P1313 ─> head-of-government office
territory ── P1906 ─> head-of-state office
territory ── P6/P35 ─> current person (churns; never the anchor)

legislature ── P527 ─> membership office ⇄ P361
chamber ── P361 ─────> whole legislature (bicameral)
legislative term ── P13188 (qualifier on P31) ─> legislature

organization ── P2388 ─> office of its head ⇄ office ── P2389 ─> organization

person ── P39 ──> office   (person side: poliloom)
```

## 3. The country spine

Every sovereign country should have these slots filled. The spine is
the map of what a survey looks for and what a later diff compares
against; the survey itself only records what it finds per slot,
including absence.

| Slot | Found via | Expected target kind |
|---|---|---|
| head-of-state office | country `P1906` | office item |
| head-of-government office | country `P1313` | office item (may coincide with head of state in presidential systems) |
| legislature | country `P194` | legislature item — never a government or cabinet |
| chambers (bicameral) | legislature `P527` ⇄ chamber `P361` | lower/upper house items |
| membership office (per chamber) | body `P527` ⇄ office `P361` | durable office — the P39 target |
| cabinet / government | research | enduring cabinet class; government organization |

Current persons (`P6`/`P35`) churn and go stale; the office pointers
above are the durable constitutional anchors. Ministries and courts
extend the national spine; below the country, the same spine recurses
per jurisdiction — see 'Deeper levels of government' below.

### Institution recipes (Parliaments model)

**Unicameral legislature:**

```text
P31   unicameral legislature (Q37002670)
P17   sovereign country
P1001 actual jurisdiction (differs from P17 only subnationally)
P527  the membership office
P1342 number of seats — dated qualifiers when it changes, current
      count at preferred rank
```

**Multi-house legislature and chambers:**

```text
legislature:  P31 legislature (Q189445); P527 each chamber
chamber:      P31 lower house (Q375928) / upper house (Q637846), or a
              country-specific subclass; P361 the whole; P1342 seats
```

Country `P194` → the legislature (a single umbrella value — §7.5).

### Office recipes

**Legislature membership office:**

```text
P31   position (Q4164871)  (preferred; public office (Q294414) is common — §7)
P279  member of parliament (Q486839) or suitable role family
P17   sovereign country
P1001 actual territorial jurisdiction
P361  immediate body: the chamber (bicameral) or whole legislature
P571  inception, if known
```

Term, district, and party of an individual mandate belong on the
person's P39 statement (poliloom), not on the office.

**Head-of-state / head-of-government office:**

```text
P31   position (Q4164871)   (Q294414 and title-class P31 also occur — §7)
P279  head of state / head of government, directly or via prime minister
P17   sovereign country
P1001 actual jurisdiction
P2097 normal term length, where applicable
```

A title like "president" is not evidence of head-of-state function;
classify the constitutional function, sourced.

**Cabinet-level ministerial office:**

```text
P31   position (Q4164871)  (preferred; public office (Q294414) still leads here — §7)
P279  minister (Q83307) or more specific minister class
P17   sovereign country
P1001 actual jurisdiction
P361  enduring cabinet  (junior/non-cabinet offices: the government)
P2389 ministry or organization directed, where applicable
P571/P576, P1365/P1366  when the office was created/abolished/replaced
```

**Ministry / agency** (an institution — never a P39 value):

```text
P31   most specific country-specific organization type
P17 / P1001   country and jurisdiction
P749  parent organization; P355 children
P2388 office held by its head (inverse of P2389)
P571/P576 lifecycle
```

### Link closure

- office `P361` → its **immediate** body;
- legislature/chamber `P527` ⇄ membership office `P361`;
- individual legislative term: `P31` the term type (or
  `Q15238777` with a `P13188` → legislature **qualifier on that P31**
  statement), plus `P571`/`P576` and `P1365`/`P1366` succession;
  direct `P13188` belongs on the generalized term class;
- legacy term-specific membership offices must `P279` the durable
  membership office;
- organization `P2388` ⇄ office `P2389`;
- individual cabinets: `P31` the enduring cabinet class, `P571`/`P576`,
  chained `P1365`/`P1366`. A person's participation in a cabinet belongs
  on their P39 as `P5054` (poliloom side).

### Deeper levels of government

The spine recurses per jurisdiction: the same four-way separation and
the same recipes apply at each level, with `P1001` narrowing (§4).

- **first-level subdivisions** (states, provinces, regions): own
  legislature + membership office + executive offices;
- **municipalities**: the council as institution, its membership
  office, and the executive — the mayoralty is an office with `P1001`
  the municipality;
- **special-purpose governments** (water boards and similar functional
  authorities): the governing board as institution, its membership
  office, its chair office; `P1001` the district.

Type every body with the most specific class available; the
established class roots are city council (Q3154693) with
country-specific subclasses (city assembly in Japan, urban council in
Ukraine, …), mayor (Q30185) for mayoralties, and country classes such
as water board in the Netherlands (Q702081) for special-purpose
bodies. The municipal constitutional anchor is established practice:
municipality `P1313` → the mayoralty office (~60k municipalities),
while `P6` → the current mayor churns.

No upstream WikiProject prescribes local-level modeling — the
recursive spine above *is* the desired model, and current practice is
thin and uneven (QLever 2026-07): only ~900 municipal councils carry
council typing at all (and ~90 link a membership office), and water
boards exist as plain institution items with no office structure. The
57k mayoralties are mostly legacy flat titles — `P17` the country, no
`P1001`, no `P31`, no `P361` — while a recent wave (e.g. the Dutch
mayors) follows the full recipe. Treat flat local items as incomplete
data to repair toward the recipe, never as an alternative model.

Surveys cover the subnational levels in aggregate; completeness work
descends level by level.

Constituencies and elections are adjacent, person-side structures:
electoral district items are `P31` electoral district (Q192611) with
`P131` the enclosing territory (their legislature link, formerly
`P642`, is unsettled upstream — §6); elections are events with `P541`
office contested → the office. Both are poliloom-side coverage, but
their items point at offices and surface in surveys.

## 4. Jurisdiction: `P17` is not `P1001`

`country (P17)` is the sovereign state the subject is situated in
(never used on humans). `applies to jurisdiction (P1001)` is the
territory the institution or office has power over — a country, state,
province, or municipality.

| Office | `P17` | `P1001` |
|---|---|---|
| national office of Spain | Spain | Spain |
| member of the Oregon State Senate | United States | Oregon |
| member of the People's Assembly of Dagestan | Russia | Dagestan |
| municipal mayoralty | sovereign country | municipality |

At national level the values coincide; that does not make the
properties interchangeable. Subnational offices keep `P17` = sovereign
country and `P1001` = subdivision. The exact historical state entity
matters (PRC vs British Hong Kong; a Soviet republic vs the USSR).

Jurisdiction is not location: never substitute `P131`, `P159`, or
`P276` for `P17`/`P1001`.

**Duplication, not inheritance.** The WikiProject recipes deliberately
expect `P17`/`P1001` on both a body and its membership office — each an
independently sourced statement about that item. Nothing inherits
through `P361`: the body's claims and references describe the body.
An office without jurisdiction statements is a research gap.

### Not political offices — common false positives

- **Religious offices** (bishops etc.): `P17` often denotes location,
  not governing jurisdiction.
- **Diplomatic offices** (ambassadors to a country): `P17` denotes the
  country of accreditation.
- **Generic occupations** (mayor, judge, professor, president,
  senator, minister without country): no unique jurisdiction — must
  never receive country scope, however many holders they have.
- **Professional associations and companies**: `P17` is the country of
  incorporation or membership, not a political office.
- **Wikimedia list articles, disambiguation pages, legislative terms,
  cabinets** appearing as P39 values: contamination that signals a
  missing or mis-modeled position item.

## 5. Lifecycle and history

Entity lifecycle uses `P571`/`P576`; the truth interval of a statement
or tenure uses `P580`/`P582` qualifiers (person side — poliloom).

- **Renamed but continuous** institution: same item, `P1448` with time
  qualifiers.
- **Actually abolished**: keep its statements, add `P576`;
  `P1365`/`P1366` for real functional replacement (`P155`/`P156` is
  mere sequence). Accurate old data stays at normal rank — deprecated
  rank is for what was never true.
- **Genuinely different successor**: a distinct item, not recycling the
  old one.
- **Historical states are distinct entities.** An office's `P17` must
  be period-correct; never project the modern state backward. One
  office item carrying `P17` values from mutually exclusive historical
  states is regime conflation — suspect a split is needed.
- An office whose holders all have end dates but which lacks `P576`
  may indicate an abolished office — a lead to research, not proof.
- `historical position (Q114962596)` is an accepted type for abolished
  offices; it is not a basis for mass retyping.

## 6. Variation and disagreement

Legitimate national variation — register it in surveys, never "fix" it:

- **presidential systems**: `P1313` and `P1906` may name the same
  office;
- **bicameral**: membership office `P361` the chamber; **unicameral**:
  `P361` the whole legislature;
- **monarchies**: the head-of-state office is the crown; persons churn
  in `P35`;
- **collective head of state**: the office may be a collegial body
  (Swiss Federal Council, Bosnia's tripartite presidency); the chair
  rotates and is not the office;
- **legacy term-specific membership offices**: supported where
  established, never adopted anew; person statements must still carry
  `P2937`;
- **non-term systems**: tenure dated with `P580` only;
- **consecutive mandates**: one continuous statement vs one per
  mandate — both documented (person side).

Known unresolved points — never mass-normalize across them:

- `P361` vs `P749`: structural part-whole vs organizational
  subordination — pick the intended fact, don't assert both;
- the multilevel shape of office typing itself (challenged upstream in
  2025, unanswered — see §7.1);
- constituency modeling: `P642` on electoral districts is deprecated
  with no agreed replacement recorded.

For systematic conversion in a country with an established divergent
model, discuss with the relevant WikiProject first.

## 7. Project positions on contested points

Where upstream sources disagree, this project commits to one side —
our stance, revisited if upstream settles. Usage figures are QLever
snapshots (2026-07).

1. **Office typing: `P31` position (Q4164871) + `P279` the role
   family, for every office.** The every-politician model prescribes
   `P31` public office (Q294414) for membership and ministerial
   offices; the Heads model prescribes Q4164871 for head offices. Live
   practice sides with Q4164871 nearly everywhere: head offices 47.6k
   vs 6.7k, membership offices 3.2k vs 0.2k; only ministerial offices
   lean Q294414 (6.3k vs 2.6k). One type for all offices is one
   queryable pattern, so we follow the majority. Existing Q294414 (and
   the title-class-as-`P31` mayor pattern) are legitimate — never
   mass-retype. A 2025 talk post challenges the whole
   `P31`-class + `P279`-role shape as broken multilevel modeling
   (proposing `P31` the role class); it is unanswered and we do not
   adopt it.
2. **Always the specific office item within political scope.** An open
   RFC (P2389 as qualifier) proposes person `P39` → a generic
   leadership office + `P2389` → the organization instead of minting
   office items; ~59k P39 statements already use it. That pattern
   serves non-political organizational leadership (director of museum
   X); political offices with a jurisdiction are this project's reason
   to exist, so we always create the specific item. Do not mass-remove
   the qualifier pattern outside our scope either.
3. **Cabinet composition is person-side; our cabinet edge is office
   `P361`.** Individual cabinets carry `P527` → people in practice
   (3.8k vs 0.1k offices; a minister without portfolio exists only as
   a person). Rosters on episodes are tenure data — poliloom
   territory. What we maintain: cabinet-level office `P361` → the
   enduring cabinet class; junior office `P361` → the government.
4. **`P1308` only where constrained or curated.** It is 1.3% of P39
   volume and disputed as a roster. Keep or add it where the
   P1906/P1313 constraint demands it (head offices) or a curated
   historical holder list exists; never mass-populate from P39, never
   strip as "duplication".
5. **One `P194` to the umbrella legislature where one exists;
   multi-`P194` is legitimate divergence.** P194's documentation wants
   jurisdiction → one collective legislature, chambers via its `P527`,
   `P3113` for no legislature. 51 entities point `P194` directly at
   several chambers (Germany, Switzerland among them) — established
   practice we register, never "fix" by synthesizing umbrella items.

## Sources

Principal models:

- [WikiProject every politician — Political data model](https://www.wikidata.org/wiki/Wikidata:WikiProject_every_politician/Political_data_model) — cross-country office guidance (work in progress)
- [WikiProject every politician — P39 model](https://www.wikidata.org/wiki/Wikidata:WikiProject_every_politician/P39_model) — person-side tenure model (poliloom context)
- [WikiProject Parliaments](https://www.wikidata.org/wiki/Wikidata:WikiProject_Parliaments) — legislature, chamber, term, membership-office recipes
- [WikiProject Heads of state and government — Data Model](https://www.wikidata.org/wiki/Wikidata:WikiProject_Heads_of_state_and_government/Data_Model) — territory–office–holder graph
- [WikiProject Govdirectory — Data model](https://www.wikidata.org/wiki/Wikidata:WikiProject_Govdirectory/Data_model) — ministries, agencies, organizational hierarchy (draft)

Core properties and help:

- [P39 position held](https://www.wikidata.org/wiki/Property:P39) ·
  [P17 country](https://www.wikidata.org/wiki/Property:P17) ·
  [P1001 applies to jurisdiction](https://www.wikidata.org/wiki/Property:P1001) ·
  [P361 part of](https://www.wikidata.org/wiki/Property:P361) ·
  [P527 has part(s)](https://www.wikidata.org/wiki/Property:P527) ·
  [P194 legislative body](https://www.wikidata.org/wiki/Property:P194) ·
  [P2388](https://www.wikidata.org/wiki/Property:P2388)/[P2389](https://www.wikidata.org/wiki/Property:P2389) office–organization ·
  [P13188 meeting of](https://www.wikidata.org/wiki/Property:P13188)
- [Help:Basic membership properties](https://www.wikidata.org/wiki/Help:Basic_membership_properties) — P31/P279/P361 semantics
- [Help:Property constraints portal](https://www.wikidata.org/wiki/Help:Property_constraints_portal) — hints, not firm restrictions
- [historical position (Q114962596)](https://www.wikidata.org/wiki/Q114962596)

Country pages of these WikiProjects are unevenly maintained and their
titles are not predictable from the country name: the snapshot index
`wikiproject-pages.txt` (next to this file) lists which exist,
including talk pages; regeneration recipe in its header.

Evidence of unresolved practice (not guidance):

- [Talk: every politician Political data model](https://www.wikidata.org/wiki/Wikidata_talk:WikiProject_every_politician/Political_data_model)
- [Property talk: P39](https://www.wikidata.org/wiki/Property_talk:P39) — maintained constraint: specific office preferred over generic + qualifier
- [Property talk: P194](https://www.wikidata.org/wiki/Property_talk:P194) — single-umbrella legislature model, `P3113` alternative
- [Property talk: P1308](https://www.wikidata.org/wiki/Property_talk:P1308)
- [RFC: Use of P2389 as a qualifier](https://www.wikidata.org/wiki/Wikidata:Requests_for_comment/Use_of_P2389_as_a_qualifier) — open dispute on generic leadership offices
