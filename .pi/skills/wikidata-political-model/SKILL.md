---
name: wikidata-political-model
description: How political offices, institutions, officeholders, legislative terms, and jurisdictions are modeled on Wikidata. Use when querying, judging, or proposing edits to political position items (P39 values), legislative bodies, cabinets, ministries, or territorial jurisdiction statements like P17 and P1001.
---

# Wikidata political data model

There is no single immutable Wikidata schema for political data. Authority order:
property definitions and Help pages → WikiProject models (Every Politician,
Parliaments, Heads of state and government) → property constraints (hints, not
firm restrictions) → established country-specific practice.

## The central rule: keep four things separate

1. **territorial jurisdiction** — a country, state, province, municipality
2. **political institution** — a legislature, chamber, government, cabinet, ministry
3. **office/position** — mayor of a city, member of a chamber, a ministerial portfolio
4. **officeholder** — the person holding the office during one or more periods

A fifth object, a **legislative term or individual cabinet**, is a time-bounded
episode — neither the enduring institution nor an office.

Most political-data errors come from collapsing these: using a legislature,
cabinet, ministry, list article, generic occupation, or legislative term as a
person's `position held (P39)` value.

## Frequently useful patterns

- `office ──P361──> institution/body`, `chamber ──P361──> whole legislature`
- `office ──P2389──> organization it directs`, inverse `organization ──P2388──> office`
- A specific national office should carry `country (P17)` and/or
  `applies to jurisdiction (P1001)`; generic roles (president, senator) must not.
- If a position is `P31 = Q294414` (public office) with exactly one `P361` body
  and no P17/P1001, and that body has exactly one non-deprecated P17 and P1001,
  the paired P17+P1001 backfill is usually safe — propose both together.
- `instance of (P31)` = one thing belongs to a class; `subclass of (P279)` =
  every instance does; `part of (P361)` = component of a whole. Do not mix them.

## Reference

See [references/model.md](references/model.md) for the full modeling reference,
including ontology details, per-topic recipes (legislatures, executives,
cabinets, terms), property tables, and cited sources.
