---
name: wikidata-labels
description: How Wikidata labels, aliases, descriptions, the mul language code, and language fallback work. Use when displaying entity names, choosing a label language for presentation, or judging whether a label/edit involving labels or aliases is appropriate.
---

# Wikidata labels and fallback

Key facts when working with entity terms:

- A label is the name of an entity **in a particular language**; it is
  multilingual, may be ambiguous, and is disambiguated by the description.
- Labels in different languages may be unrelated. A label is not guaranteed
  to be an English name, a translation, or a Wikipedia title.
- `mul` ("multiple languages") is the default-for-all-languages label/alias,
  enabled by default since 2025-01-28. Use it only for terms genuinely
  identical across many languages — it is not a licence to replace every label.
- Language fallback chains can pass through several languages before `mul`
  and English. Preserve the language code alongside any term you display;
  the QID remains the only stable reference.

## Reference

See [references/labels.md](references/labels.md) for documented fallback
behaviour, Termbox details, and project-specific display advice, with sources.
