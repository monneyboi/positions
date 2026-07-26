# Modeling political offices and institutions on Wikidata

**Research date:** 2026-07-24  
**Scope:** political offices used as values of `position held (P39)`, the institutions to which those offices belong, officeholders and tenures, legislative terms, cabinets, governments, ministries, and territorial context.

## 1. Status and governing principle

There is no single immutable Wikidata schema for political data. The closest thing to a cross-country prescription is [WikiProject every politician's Political data model][S1]. It explicitly describes itself as a **work in progress**. This document therefore uses the following order of authority:

1. the definitions of Wikidata properties and general Help pages;
2. topic-specific WikiProject models, especially Every Politician, Parliaments, and Heads of state and government;
3. property constraints as quality-control hints;
4. established country-specific practice when the general model explicitly permits alternatives; and
5. talk-page discussions only as evidence of unresolved questions, not as settled guidance.

The word “mandatory” below means mandatory **within a cited WikiProject recipe**, not mandatory under an immutable Wikidata policy. Wikidata's own constraints are also “hints, not firm restrictions” and can have valid exceptions.[S24]

The central modeling rule is to keep four different things separate:

1. **territorial jurisdiction** — a country, state, province, municipality, etc.;
2. **political institution** — a legislature, chamber, government, cabinet, ministry, or agency;
3. **office or position** — mayor of a particular city, member of a particular chamber, a particular ministerial portfolio; and
4. **officeholder** — the person who holds the office during one or more periods.

A fifth object, a **legislative term or individual cabinet**, represents a time-bounded institutional episode. It is not the enduring institution and not an office.

A simplified graph is:

```text
territory ── P194 ──> legislature
territory ── P1313 ─> head-of-government office
territory ── P1906 ─> head-of-state office
territory ── P6/P35 ─> current person

legislature ── P527 ─> membership office
chamber ── P361 ─────> whole legislature
membership office ── P361 ─> legislature or chamber
legislative term ── P13188 ─> legislature

organization ── P2388 ─> office that heads it
office ── P2389 ───────> organization it directs

person ── P39 ─────────> office
         qualifiers: P580, P582, P2937, P5054, P768, P4100, …
office ── P1308 ───────> person (inverse/optional duplication in practice)
```

This separation is the main defense against common errors such as using a legislature, cabinet, ministry, list article, generic occupation, or legislative term as a person's `P39` value.

---

## 2. Ontology: instance, subclass, and part

General Wikidata ontology distinguishes three relations:[S6]

| Property | Meaning | Political example |
|---|---|---|
| `instance of (P31)` | one particular thing belongs to a class | the Parliament of Finland is an instance of unicameral legislature |
| `subclass of (P279)` | **every** instance of one class is also an instance of another class | a country-specific ministerial role is a subclass of minister |
| `part of (P361)` | one thing is a component of a larger whole | a chamber is part of a bicameral legislature; an office is part of its cabinet/body in the political model |

`P279` and `P361` are transitive, but their meanings are different. `P361` does not make the subject an instance or subclass of its object. Nor does transitivity create general property inheritance: if an office is part of a body, the body's `P17`, `P1001`, dates, references, or rank do **not** logically become statements about the office.

For a named, jurisdiction-specific office, the domain guidance commonly combines:

```text
specific office
  P31  public office or position
  P279 general role family (minister, member of parliament, head of government, …)
  P361 immediate political body, where that relationship is applicable
```

Do not classify by label alone. “President” is not necessarily a head of state, and the P39 constraints explicitly discourage generic values such as generic minister, deputy, or country-unspecific parliamentary roles when a specific office exists.[S4][S7]

### 2.1 A live inconsistency: `Q294414` versus `Q4164871`

Two strong WikiProject models prescribe different direct `P31` values:

- Every Politician says legislature-membership and cabinet-level office items should have `P31 = public office (Q294414)`.[S1]
- The Heads of state and government model says every specific head-of-state or head-of-government office should have `P31 = position (Q4164871)`.[S4]

`position (Q4164871)` is broader than the political/public-office concept. The two recipes are directionally compatible but not reconciled at the direct-statement level. Current item and property constraints also evolve over time. Consequently:

- do not replace one direct type with the other automatically;
- follow the relevant domain or established national model;
- do not assume direct `P31 = Q294414` discovers all valid political offices;
- treat exact direct typing as a conservative workflow filter, not a complete ontology definition; and
- inspect the item's full class path before claiming that its `P31` is wrong.

`historical position (Q114962596)` is also accepted by the current `P39` value-type constraint for an office that no longer exists.[S7][S29] This newer ontology is not fully reconciled with the older WikiProject tables, so it is not a basis for blind mass retyping.

---

## 3. Territorial context: `P17` is not `P1001`

### 3.1 Country

`country (P17)` identifies the sovereign state in which the subject is situated. It is not for humans.[S9] For political institutions and offices it provides sovereign-country context.

The exact state entity matters, especially historically. The P17 property constraints call out examples such as:

- People's Republic of China versus British Hong Kong before/after 1997;
- People's Republic of China versus Portuguese Macau before/after 1999;
- a particular Chinese state rather than ambiguous “China”;
- a particular ancient polity rather than “Ancient Greece”; and
- a sovereign state rather than a region, government, or international organization.[S9]

### 3.2 Applies to jurisdiction

`applies to jurisdiction (P1001)` identifies the territorial jurisdiction to which an institution, law, or public office belongs, over which it has power, or to which it applies. It can be a country, state, province, municipality, or another territorial jurisdiction.[S10]

Thus:

| Office | `P17` | `P1001` |
|---|---|---|
| national office of Spain | Spain | Spain |
| member of the Oregon State Senate | United States | Oregon |
| member of the People's Assembly of Dagestan | Russia | Dagestan |
| municipal mayoralty | sovereign country | municipality |

At national level the values often coincide. That coincidence does not make the properties interchangeable.

### 3.3 Jurisdiction is not location

Do not substitute these location properties for jurisdiction:

- `located in the administrative territorial entity (P131)` — where an item is geographically located;
- `headquarters location (P159)` — where an organization is headquartered;
- `location (P276)` — a location appropriate to the subject.

A national agency can have headquarters in one municipality while exercising national jurisdiction. Conversely, a subnational office's `P1001` is the region over which it has authority, not merely the building's location.[S5][S10]

### 3.4 Explicit duplication, not inheritance

The Every Politician and Parliaments recipes deliberately expect `P17` and `P1001` on both a legislature/body and its membership office.[S1][S3] This duplication helps queries and consistency checks. It is still an explicit set of claims on two items, not a formal inheritance rule.

Therefore this inference is **not valid without review**:

```text
office P361 body
body P17 country
body P1001 jurisdiction
∴ office automatically has the same P17 and P1001
```

It is a useful candidate-generation heuristic only. It can fail for historical succession, sovereignty changes, institutions spanning jurisdictions, delegated or non-territorial roles, an incorrect `P361`, an overly broad body, or a position whose scope differs from the body's general scope.

---

## 4. Legislatures, chambers, terms, and membership offices

The Parliaments and Every Politician models distinguish four entities.[S1][S3]

### 4.1 Enduring legislature

For a unicameral legislature, the Parliaments recipe calls for:

| Property | Value |
|---|---|
| `P31` | `unicameral legislature (Q37002670)` |
| `P17` | sovereign country |
| `P1001` | territorial jurisdiction |
| `P527` | the legislature's membership-office item(s) |

Useful additional facts include `P1342` seat count, `P4253` constituency count, `P571` inception, `P276` location, and `P856` official website.[S3]

For a bicameral or multichamber legislature:

```text
whole legislature
  P31  bicameral legislature (Q189445), or appropriate type
  P527 lower/upper chambers

chamber
  P31  lower house (Q375928), upper house (Q637846), or subclass
  P361 whole legislature
```

A country or territory points to its governing legislature with `legislative body (P194)`, not with `P361` or `P355`.[S3][S17]

For subnational legislatures, `P17` remains the sovereign country and `P1001` is the subnational jurisdiction. The Parliaments model gives Brandenburg as the pattern and warns editors to choose constitutionally correct country entities.[S3]

### 4.2 Legislative term

A legislative term is a time-bounded meeting/term of an enduring legislature. It should not be conflated with the legislature or the membership office.

The Parliaments recipe permits either:

- `P31` a legislature-specific legislative-term class; or
- `P31 = legislative term (Q15238777)` plus `meeting of (P13188)` the legislature.[S3][S18]

A term should carry:

| Property | Meaning |
|---|---|
| `P571` | date the term began, usually not election day |
| `P576` | date it ended; omit while current |
| `P17` | sovereign country |
| `P1001` | jurisdiction |
| `P1365` / `P1366` | term it replaces / is replaced by, ideally |
| `P1342` | number of seats, when known |

`P155/P156` and term-level `P580/P582` are documented as legacy patterns to migrate to `P1365/P1366` and `P571/P576` respectively.[S3]

For a bicameral term, qualify a seat-count statement with `applies to part (P518)` to identify the chamber. A numbered term may qualify its `P31` with `series ordinal (P1545)`.[S3]

A generalized country-specific **term class** is itself a class, so its recipe is `P279 = legislative term`, `P13188` legislature, `P17`, and `P1001`.[S3]

### 4.3 Membership office

A durable office such as “member of the Parliament of Finland” is the preferred `P39` target. Every Politician's recipe is:[S1]

| Property | Value |
|---|---|
| `P31` | `public office (Q294414)` |
| `P279` | `member of parliament (Q486839)` or another suitable role family |
| `P17` | sovereign country |
| `P1001` | actual national or subnational jurisdiction |
| `P361` | the legislature or chamber to which membership belongs |
| `P571` | office inception, if known |

The enduring legislature can point back with `P527`.

In a bicameral system, the immediate body should usually be the chamber whose membership the office represents, rather than only the whole parliament. This follows both the direct-parent principle of `P361` and the Parliament project's chamber structure.[S3][S11]

### 4.4 Per-term membership offices and list articles

New modeling should generally use one durable membership office and put the term on the person's `P39` statement with `P2937`.[S1][S2]

Some countries have legacy term-specific office items. Every Politician calls these an earlier tooling workaround and says not to adopt the pattern anew unless that legislature already uses it. Where retained:

- the term-specific office must have `P279` to the durable membership office; and
- each person's `P39` must still carry `legislative term (P2937)`.[S1]

A “list of members” article is neither the term nor the membership office. The Parliaments model instead types it as `Wikimedia list article (Q13406463)` and uses `is a list of (P360)` the membership office, qualified by `P2937` the term; the term may link back with `has list (P2354)`.[S3] A list article must not be used as a `P39` value.[S7]

---

## 5. Executive institutions and offices

### 5.1 Enduring cabinet type and individual cabinets

Every Politician separates an enduring cabinet class from each time-bounded cabinet/ministry.[S1]

An enduring country-specific cabinet class uses:

| Property | Value |
|---|---|
| `P279` | `cabinet (Q640506)` |
| `P1001` | relevant jurisdiction |

Each individual cabinet then uses:

| Property | Value |
|---|---|
| `P31` | the country-specific cabinet class |
| `P1001` | jurisdiction |
| `P571` | formation date |
| `P576` | end date, omitted while current |
| `P527` | cabinet members/parts under the established national model |
| `P1365` / `P1366` | predecessor/successor cabinet, preferably |

The object of cabinet `P527` is disputed. The principal model's table says “members,” while its talk page records competing office-based and person-based models without resolution.[S25] Preserve an established national model and do not bulk-convert cabinets between these representations without consensus. The stable person-side representation is `P39` qualified by `member of cabinet (P5054)`.

### 5.2 Cabinet-level ministerial office

Every Politician's recipe for a specific cabinet-level portfolio is:[S1]

| Property | Value |
|---|---|
| `P31` | `public office (Q294414)` |
| `P279` | `minister (Q83307)` or a more specific minister class |
| `P17` | sovereign country |
| `P1001` | geographic jurisdiction |
| `P361` | enduring cabinet |
| `P2389` | ministry or organization directed by the office, where applicable |
| `P571` / `P576` | creation/abolition dates, when known |
| `P1365` / `P1366` | predecessor/successor office when there was real replacement |

The office belongs to the enduring cabinet model; an individual holder's participation in a particular named cabinet belongs on that person's tenure as `P5054`.

For junior or non-cabinet ministerial positions, the model says `P361` should point to the government rather than the cabinet.[S1]

### 5.3 Government, ministry, and agency

A government organization is not an office. Govdirectory, whose global agency model is also explicitly a draft, recommends the most specific country-specific organization type available rather than only generic “ministry” or “government agency.”[S5]

Typical organization facts include:

| Property | Meaning |
|---|---|
| `P31` | specific organization/agency type |
| `P17` | sovereign country |
| `P1001` | territorial jurisdiction |
| `P101` | field of work |
| `P571` / `P576` | inception/dissolution |
| `P749` | parent organization or unit |
| `P2388` | office held by the organization's head |
| `P488` | chairperson, where appropriate |
| `P1313` | office held by head of government, where appropriate |
| `P355` | child organization or unit |

For an abolished body, retain its historical statements and add `P576`. Use `P1365/P1366` for a real functional replacement; use `P155/P156` only for mere sequence rather than replacement.[S5]

### 5.4 Office–organization direction

These inverse properties connect an office to the organization it leads:

```text
organization P2388 office
office       P2389 organization
```

`P2388` means **the position held by the organization's head**. Its value is an office, not the current officeholder.[S15] `P2389` means the organization or project directed by an office.[S16] Neither property expresses territorial jurisdiction or generic organizational parentage.

### 5.5 Organizational hierarchy versus part-whole

Use the most specific supported relation:

- `P749` / `P355` — parent and child organization or organizational unit;
- `P361` / `P527` — broader compositional part and whole;
- `P194` — territory to legislature;
- `P2388` / `P2389` — organization to the office that heads it;
- `P13188` — term/session to the organization of which it is a meeting.

`P749` is itself modeled as a subproperty of both ownership and `P361`, so the boundary with generic part-whole is not perfectly crisp.[S13] Talk-page discussion remains unresolved. A practical synthesis is:

- use `P749/P355` for organizational subordination, especially agencies and units;
- use `P361/P527` for constitutional or structural composition such as chamber–legislature and office–cabinet/body where the political WikiProjects prescribe it;
- use only the immediate parent/whole where that parent is itself nested; and
- do not assert both pairs merely for redundancy.

---

## 6. Heads of state and government

The Heads of state and government WikiProject intentionally stores redundant routes among territory, office, and person because this makes queries easier and discrepancies visible.[S4]

### 6.1 Territory-side statements

| Function | Current person | Office |
|---|---|---|
| head of government | `head of government (P6)` | `office held by head of government (P1313)` |
| head of state | `head of state (P35)` | `office held by head of state (P1906)` |

The person and office are different values. Do not put an office in `P6/P35` or a person in `P1313/P1906`.

### 6.2 Office-side statements

The Heads project prescribes:

| Property | Value |
|---|---|
| `P31` | `position (Q4164871)` |
| `P279` | head of state/head of government, directly or through a more specific role such as prime minister |
| `P17` | sovereign country |
| `P1001` | national or subnational jurisdiction |
| `P2097` | normal term length, where the model applies |

Possible additional office facts include a deputy office (`P2098`), official residence (`P263`, time-qualified when it changes), official website, lists, and categories.[S4]

A title such as “president” is not sufficient evidence that an office is a head of state. Classify the constitutional function explicitly and source it.

### 6.3 Person-side and office-side holder links

The person uses `P39` to the office, with tenure qualifiers. `position holder (P1308)` is formally inverse to `P39`; its property page allows current and former holders, requires temporal context through a `P585` constraint, and accepts tenure-related qualifiers.[S8]

The Heads project favors redundant holder routes, but the practical scope of `P1308` is disputed on its talk page: editors disagree about maintaining it for all holders, only offices with few simultaneous holders, or only selected notable offices.[S26] Therefore:

- `P39` is the primary and universally useful holder representation;
- if `P1308` is used, keep it consistent with `P39` and supply the required temporal context;
- do not infer that an unqualified `P1308` is current merely from its label; and
- do not generate huge office-side rosters without checking the established model and maintenance cost.

---

## 7. Modeling a person's tenure with `P39`

`position held (P39)` means that the subject currently or formerly holds the value position.[S7] For political office:

- use `P39`, not `member of (P463)`;
- prefer the most specific real office item;
- do not use the political institution, term, cabinet, or list article as the value;
- do not substitute an occupation (`P106`) for a distinct office; and
- use a generic value only as an acknowledged incomplete fallback when no specific office exists and local practice permits it.

### 7.1 Tenure qualifiers

Common qualifiers include:[S1][S2][S7]

| Qualifier | Meaning |
|---|---|
| `P580` | start of this tenure/statement context |
| `P582` | end of this tenure; omit while current |
| `P2937` | legislative term |
| `P5054` | individual cabinet |
| `P768` | electoral district |
| `P4100` | parliamentary group |
| `P2715` | election in which the mandate was obtained |
| `P1534` | cause of ending |
| `P1365` / `P1366` | predecessor/successor person or tenure context where semantically appropriate |
| `P1545` | series ordinal, such as ordinal officeholder number |
| `P805` | separate item about the tenure, if one already exists |
| `P1001` | statement-specific jurisdiction where needed |

These are allowed or recommended where applicable; they are not all universally required. A source must support the qualifier as well as the main value.

`P1001` can legitimately be statement-specific. Wikidata's qualifier guidance gives a political example in which a person's `P39` is refined by the relevant municipality.[S21] This does not replace well-modeled jurisdiction on a specific office item, but it is useful when the same role item spans contexts or the jurisdiction belongs to the tenure rather than timelessly to the office.

### 7.2 One statement or several

Create separate `P39` statements when:

- there is a gap between tenures;
- legislative term, cabinet, district, parliamentary group, or another material qualifier changes; or
- separate mandates need separately sourced dates or context.[S1][S2]

Do not put multiple start dates, end dates, legislative terms, or cabinets on one statement to encode separate periods. Qualifiers refine the main statement; they do not pair with one another.[S21]

For consecutive re-election or reappointment, Every Politician documents two valid practices:

1. one continuous statement for the whole uninterrupted period; or
2. one statement per mandate, enabling richer term-specific data.

Follow established national practice and discuss before mass-converting between these models.[S1]

For a current holder, omit `P582`; do not set it to `novalue`.[S1][S2] Preserve date precision and calendar model, especially for historical dates, and do not invent day-level precision from a source that gives only a year.[S22]

---

## 8. Time, changing institutions, and historical offices

Use different properties for entity lifecycle and statement validity:

| Context | Start | End |
|---|---|---|
| office, institution, cabinet, or legislative term exists | `P571` | `P576` |
| a claim or tenure is true during an interval | `P580` qualifier | `P582` qualifier |
| a value applies at one time | `P585` qualifier | — |

Accurate old information is not deprecated merely because it is old. It should normally remain at normal rank with dates or other temporal context. Deprecated rank is for a value known to be erroneous or representing outdated knowledge that was not actually true, and it must still be verifiable as a published claim.[S23]

For institutional change:

- use `P1448` with time qualifiers for an official-name change when identity continues;
- add `P576` when the institution or office really ceases to exist;
- use `P1365/P1366` for actual replacement, including one-to-many replacement where appropriate;
- do not use replacement merely because two similarly named offices occur in sequence; and
- create a distinct item when sources and constitutional continuity indicate a genuinely different office or institution, not merely a renamed one.[S5]

Historical `P17` and `P1001` values may require `P580/P582/P585` and period-correct entities. A modern body's country claim cannot safely be projected backward onto an abolished office. Similarly, a historical office is not made “current” by preferred rank; current-value ranking conventions for non-historical country heads do not automatically apply to all `P39` history.

---

## 9. Ranks, queries, and validation

Ranks and references answer different questions:[S23]

- **normal** — neutral/default and normally appropriate for valid historical facts;
- **preferred** — current or best-consensus value(s), ideally sourced and qualified;
- **deprecated** — erroneous or superseded knowledge, not simply former values.

There is no universal rule that every current `P39` must be preferred. In fact, adding one preferred `P39` can hide unrelated normal-rank positions from simple truthy queries. Use preferred rank only when its semantic purpose is clear in the relevant property/domain model.

WDQS truthy paths such as `wdt:P17` return preferred statements if any exist, otherwise normal statements, and never deprecated statements. They can therefore hide conflicts and historical values. Validation must inspect statement nodes and ranks:

```sparql
?item p:P17 ?statement .
?statement ps:P17 ?value ;
           wikibase:rank ?rank .
```

For safe editing, inspect:

- preferred, normal, and deprecated claims;
- value, `novalue`, and `somevalue` snaks;
- all qualifiers and references;
- multiple statements that agree in value but differ in time; and
- claims added after candidate extraction.

A constraint-clean item is not necessarily correct, and a constraint violation is not necessarily wrong.[S24]

---

## 10. References and verifiability

Wikidata's source guidance says the majority of factual statements should be verifiable through references to specific sources.[S19] Normally:

- use `stated in (P248)` for a publication or database represented by a Wikidata item;
- use `reference URL (P854)` for an online source;
- add `retrieved (P813)` when there is no publication date;
- preserve useful title, language, archive, page, section, and publication metadata; and
- prefer official legislation, parliamentary records, government directories, official gazettes, and reliable historical sources for political structure.

Wikidata itself cannot be cited as its own source. Wikipedia and other Wikimedia pages are not suitable underlying sources; locate the external source they cite. `imported from Wikimedia project (P143)` documents provenance but does not make a statement sourced.[S19]

The proposed Verifiability policy states the strongest version of the principle: Wikidata is a secondary knowledge base, and editors should not add original conclusions merely because other Wikidata claims appear to imply them.[S20] Its policy status is proposed, but it captures the practical risk in an inferred backfill.

### 10.1 References do not propagate through `P361`

Suppose a government body's `P17` and `P1001` claims have references. Those references support the claims **about the body**. They may be copied to an office's new claims only if the underlying publication itself also establishes the office's country or jurisdiction. The body statement and its references are not evidence by transitive inheritance.

A high-quality office reference should establish enough of the following to support the proposed claim directly:

- the office exists;
- it belongs to the named government, legislature, chamber, or cabinet;
- that institution exercises authority in the stated jurisdiction;
- the relevant sovereign country and historical period; and
- any creation, abolition, or replacement dates being asserted.

For a paired `P17/P1001` edit, one source can be attached to both claims when it directly supports both. Otherwise attach separate references. Do not add a reference merely to satisfy a mechanical “has reference” check.

---

## 11. Recommended item recipes

These recipes summarize the strongest current guidance, with its limits.

### 11.1 Legislature membership office

```text
P31   public office (Q294414)
P279  member of parliament (Q486839) or suitable role
P17   sovereign country
P1001 actual territorial jurisdiction
P361  immediate legislature/chamber
P571  inception, if known
```

Use as the person's `P39` value; put term, dates, district, and parliamentary group on the tenure.

### 11.2 Cabinet ministerial office

```text
P31   public office (Q294414)
P279  minister (Q83307) or specific minister role
P17   sovereign country
P1001 actual territorial jurisdiction
P361  enduring cabinet
P2389 ministry/organization directed, if applicable
P571/P576 and P1365/P1366 when known
```

Qualify the person's `P39` with `P5054` for the individual cabinet.

### 11.3 Junior/non-cabinet government office

```text
P31   public office (Q294414)
P279  specific role family
P17   sovereign country
P1001 actual territorial jurisdiction
P361  government rather than cabinet
P2389 directed organization, if applicable
```

This is the cited model's main recognized case for an office directly `P361` a government.[S1]

### 11.4 Head-of-state/government office

```text
P31   position (Q4164871) under the Heads project
P279  head of state/government, directly or through a specific role
P17   sovereign country
P1001 actual jurisdiction
P2097 ordinary term length, where applicable
```

Connect the territory with `P1906/P1313`, current person with `P35/P6`, and person to office with `P39`.

### 11.5 Government agency or ministry

```text
P31   most specific country-specific organization type
P17   sovereign country
P1001 jurisdiction
P101  field of work
P571/P576 lifecycle
P749  organizational parent, if any
P2388 office held by the head, if modeled
```

Do not use the organization as a `P39` value.

---

## 12. Consequences for this repository's P17/P1001 workflow

The current rule—direct `P31 = Q294414`, one `P361`, neither target property, and one non-deprecated `P17` and `P1001` value on the body—is a conservative **candidate heuristic**. It is not a Wikidata inference rule.

### 12.1 What is sound

The workflow aligns with the domain model in important ways:

- it edits the office item rather than the person;
- it requires a specific public-office item;
- it keeps `P17` and `P1001` separate;
- it uses the office's explicit structural body rather than a label-only guess;
- it requires human approval;
- it re-fetches live entities and validates all ranks before submission;
- it submits the paired context atomically; and
- it avoids generic offices such as senator or president that have no unique jurisdiction.

The WikiProject recipes explicitly expect these two claims on legislature-membership and ministerial-office items, even when the corresponding body also carries them.[S1][S3]

### 12.2 What remains too broad

Direct public-office typing plus one `P361` does not prove that the object is a legislature, chamber, enduring cabinet, or government. It can select:

- offices in unrelated organizations;
- misclassified items;
- offices whose immediate body is wrong or too broad;
- positions with functional or non-territorial scope;
- historical offices whose country changed; and
- office/body pairs whose jurisdictions intentionally differ.

Eligibility should therefore be limited to recognized office/body families:

1. legislative membership office → legislature or chamber;
2. cabinet-level ministerial office → enduring cabinet;
3. junior/non-cabinet political office → government;
4. any additional family only after a cited model and explicit rule are documented.

Use class paths, role type, and body type together. Do not rely on English labels or direct `P31` alone. A government body is not interchangeable with a cabinet, ministry, legislature, or agency.

### 12.3 Required temporal and rank checks

Before proposing or submitting:

- inspect every target claim at every rank, including deprecated, `novalue`, and `somevalue`;
- inspect every body `P17/P1001` statement, not only truthy `wdt:` values;
- reject multiple non-deprecated candidates unless qualifiers unambiguously select the office's lifespan;
- compare office, body, jurisdiction, and state lifecycles;
- preserve required temporal qualifiers rather than adding a false timeless value;
- reject historical-country ambiguity; and
- verify that `P361` names the genuine immediate body.

“Exactly one non-deprecated value” is not enough when that value is qualified for only part of the body's history.

### 12.4 Reference requirement

The safest submission rule is: **do not submit the pair until an external source directly supports the office's country and jurisdiction**. The source body's Wikidata claims may identify a candidate but are not the source of truth.

A review interface should expose:

- the office and body labels, descriptions, classes, dates, and revisions;
- all `P31`, `P279`, `P361`, `P17`, and `P1001` claims at all ranks;
- qualifiers and references on each relevant claim;
- the proposed external references for each new statement; and
- why the body class and office family match a documented recipe.

### 12.5 Assessment of `Q100736555`

[Secretary General of Tourism and Internal Trade (Q100736555)][S30] currently has:

```text
P31  public office
P279 general secretary
P361 Government of Spain
```

It is structurally more plausible than a generic role because it is a specific national government office, and the Every Politician model permits non-cabinet government positions to use `P361` the government.[S1] If the Government of Spain has unambiguous `P17 = Spain` and `P1001 = Spain`, the proposed pair is consistent with the expected national-office result.

It is nevertheless only a **candidate**, not a proven edit:

- the item's existing structural claims are themselves unsourced;
- `P361` does not entail the target properties;
- “general secretary” is not by itself proof of this office family; and
- an official Spanish legal or organizational source should verify that the office belongs to the Spanish national administration and has Spain-wide jurisdiction during the relevant period.

Under a source-required workflow, this proposal should remain pending until that evidence is attached.

---

## 13. Known disagreements and cautions

1. **Direct office type:** Every Politician prescribes `Q294414`; Heads prescribes `Q4164871`. Preserve the relevant model rather than mass-normalizing.
2. **Cabinet parts:** person versus office values for cabinet `P527` remain unresolved. Preserve national practice.
3. **`P1308` scope:** inverse consistency is formally encouraged, but maintaining office-side holder histories—especially for large legislatures—is disputed.
4. **Consecutive mandates:** one uninterrupted statement and one statement per mandate are both documented. Country practice matters.
5. **Term-specific offices:** still present and supported as a legacy national model, but discouraged for new adoption.
6. **`P361` versus `P749`:** structural part-whole and organizational hierarchy overlap in current modeling. Choose the relation that expresses the intended fact.
7. **Generic office boundary:** `P39` versus occupation/employer can be fuzzy outside clearly named offices. Political guidance strongly favors a distinct, jurisdiction-specific office.
8. **Current ranks:** current/preferred conventions on country-level head properties do not imply that every current `P39` should be preferred.
9. **Historical jurisdiction:** modern state identity must not be projected backward without time-aware evidence.
10. **Constraints:** useful for finding mistakes, but neither proof of truth nor immutable policy.[S24]

For systematic edits in a country with an established divergent model, discuss the intended conversion with the relevant WikiProject before changing it at scale.

---

## 14. Source register

### Principal political models

- **[S1]** [WikiProject every politician — Political data model](https://www.wikidata.org/wiki/Wikidata:WikiProject_every_politician/Political_data_model). Principal cross-country political-office guidance; explicitly a work in progress.
- **[S2]** [WikiProject every politician — P39 model](https://www.wikidata.org/wiki/Wikidata:WikiProject_every_politician/P39_model). Person-side tenure levels and recommended qualifiers.
- **[S3]** [WikiProject Parliaments](https://www.wikidata.org/wiki/Wikidata:WikiProject_Parliaments). Legislature, chamber, legislative-term, list, and membership-office recipes.
- **[S4]** [WikiProject Heads of state and government — Data Model](https://www.wikidata.org/wiki/Wikidata:WikiProject_Heads_of_state_and_government/Data_Model). Redundant territory–office–holder graph and head-office recipe.
- **[S5]** [WikiProject Govdirectory — Data model](https://www.wikidata.org/wiki/Wikidata:WikiProject_Govdirectory/Data_model). Draft global model for ministries, agencies, organizational hierarchy, and closed bodies.

### General ontology and data behavior

- **[S6]** [Help:Basic membership properties](https://www.wikidata.org/wiki/Help:Basic_membership_properties). `P31`, `P279`, and `P361` semantics and transitivity.
- **[S19]** [Help:Sources](https://www.wikidata.org/wiki/Help:Sources). Reference requirements and source forms.
- **[S20]** [Wikidata:Verifiability](https://www.wikidata.org/wiki/Wikidata:Verifiability). Proposed policy/guideline on verifiability and secondary-database status.
- **[S21]** [Help:Qualifiers](https://www.wikidata.org/wiki/Help:Qualifiers). Qualifier semantics and political jurisdiction example.
- **[S22]** [Help:Dates](https://www.wikidata.org/wiki/Help:Dates). Time precision, calendar model, and temporal qualifiers.
- **[S23]** [Help:Ranking](https://www.wikidata.org/wiki/Help:Ranking). Normal/preferred/deprecated semantics and truthy-query behavior.
- **[S24]** [Help:Property constraints portal](https://www.wikidata.org/wiki/Help:Property_constraints_portal). Constraints are guidance with exceptions, not firm restrictions.

### Core properties

- **[S7]** [`position held (P39)`](https://www.wikidata.org/wiki/Property:P39). Meaning, value types, qualifiers, and constraints favoring specific offices.
- **[S8]** [`position holder (P1308)`](https://www.wikidata.org/wiki/Property:P1308). Inverse relation, temporal qualifier constraint, and subject requirements.
- **[S9]** [`country (P17)`](https://www.wikidata.org/wiki/Property:P17). Sovereign-state meaning and historical/state-identity cautions.
- **[S10]** [`applies to jurisdiction (P1001)`](https://www.wikidata.org/wiki/Property:P1001). Territorial competence/scope and political-office examples.
- **[S11]** [`part of (P361)`](https://www.wikidata.org/wiki/Property:P361). Generic transitive part-whole relation and immediate-parent guidance.
- **[S12]** [`has part(s) (P527)`](https://www.wikidata.org/wiki/Property:P527). Inverse part-whole direction.
- **[S13]** [`parent organization or unit (P749)`](https://www.wikidata.org/wiki/Property:P749). Organizational parent relation and its relation to `P361`.
- **[S14]** [`child organization or unit (P355)`](https://www.wikidata.org/wiki/Property:P355). Organizational child relation.
- **[S15]** [`position held by head of the organization (P2388)`](https://www.wikidata.org/wiki/Property:P2388). Organization-to-office direction.
- **[S16]** [`organization directed by the office or position (P2389)`](https://www.wikidata.org/wiki/Property:P2389). Office-to-organization direction.
- **[S17]** [`legislative body (P194)`](https://www.wikidata.org/wiki/Property:P194). Territory-to-legislature relation.
- **[S18]** [`meeting of (P13188)`](https://www.wikidata.org/wiki/Property:P13188). Term/session-to-organization relation.

### Evidence of unresolved practice and current ontology

- **[S25]** [Talk: Every Politician Political data model](https://www.wikidata.org/wiki/Wikidata_talk:WikiProject_every_politician/Political_data_model). Discussion of alternative cabinet models; not binding guidance.
- **[S26]** [Property talk: P1308](https://www.wikidata.org/wiki/Property_talk:P1308). Unresolved discussion of office-side holder scope.
- **[S27]** [`position (Q4164871)`](https://www.wikidata.org/wiki/Q4164871). Current broad position item.
- **[S28]** [`public office (Q294414)`](https://www.wikidata.org/wiki/Q294414). Current public-office item.
- **[S29]** [`historical position (Q114962596)`](https://www.wikidata.org/wiki/Q114962596). Current historical-position item.
- **[S30]** [Secretary General of Tourism and Internal Trade (Q100736555)](https://www.wikidata.org/wiki/Q100736555). Current proposal example inspected for this repository.
