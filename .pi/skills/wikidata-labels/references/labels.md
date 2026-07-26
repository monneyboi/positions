# Wikidata label display and fallback reference

This note concerns **displaying existing Wikidata terms**, not choosing or writing
labels.  URLs in the “Documented behaviour” sections are the sources for the
claims there.  The final section is project-specific advice.

## Terms and scope

* A label is the main name used to represent an entity *in a particular
  language*. It is multilingual, may be ambiguous, and is normally disambiguated
  by a description. [Help:Label](https://www.wikidata.org/wiki/Help:Label)
* A label is not an identifier and is not guaranteed to be an English name, a
  translation, a Wikipedia title, or even related to the label in another
  language. Wikidata explicitly notes that labels in different languages may be
  unrelated. [Help:Label](https://www.wikidata.org/wiki/Help:Label)
* Consequently, preserve both the selected term's language code and the QID in
  a local model. A label is presentation data; the QID remains the stable entity
  reference. This is an inference from the preceding documented model.

## `mul`: “multiple languages” / default for all languages

### Documented behaviour

* `mul` is the special language code for **multiple languages**. In the UI it
  represents a “default for all languages” label or alias, rather than a label
  in a natural language. [Default values for labels and aliases](https://www.wikidata.org/wiki/Help:Default_values_for_labels_and_aliases)
* Its purpose is to store once a term that is genuinely identical across a
  plurality of languages, avoiding redundant copied labels and aliases. An
  individual language can still provide a different term. [Default values](https://www.wikidata.org/wiki/Help:Default_values_for_labels_and_aliases)
* The full release was announced as enabled by default on 28 January 2025;
  the announcement says “Default for all languages” then appears automatically
  in Termbox. Earlier testing/limited rollout was during 2024.
  [release announcement](https://lists.wikimedia.org/hyperkitty/list/wikidata@lists.wikimedia.org/message/TFPILCTX6MPYNKNWOACVBQKLKUUIVOII/)
* `mul` is part of Wikidata's language fallback chain. The project help warns
  that a language can have one or more fallbacks **before** `mul` and English.
  [Default values](https://www.wikidata.org/wiki/Help:Default_values_for_labels_and_aliases)
* Termbox was specifically updated to expose fallback values/placeholders,
  including `mul`; the release announcement says this was intended to make
  already-available fallback content visible. [announcement](https://lists.wikimedia.org/hyperkitty/list/wikidata@lists.wikimedia.org/message/TFPILCTX6MPYNKNWOACVBQKLKUUIVOII/)
* `mul` is not a licence to replace every label. The help page limits it to
  suitable cross-language terms, says not to add placeholders such as “N/A” or
  “—”, and notes that visually similar glyphs can differ across languages.
  [Default values](https://www.wikidata.org/wiki/Help:Default_values_for_labels_and_aliases)

### Tool implications

* Do not treat `mul` as missing data, a locale, or an English label. It is a
  real stored term whose intended meaning is a cross-language default.
* A client that reads raw `labels` must explicitly consider `mul`; old logic
  that selects only `en` will hide valid, UI-visible terms.
* Do not assume `en` and `mul` have identical text. The documented advice even
  notes cases where retaining English besides the default can prevent disruption.
  [Default values](https://www.wikidata.org/wiki/Help:Default_values_for_labels_and_aliases)

## Wikidata UI language fallback

### Documented behaviour

* Wikidata is multilingual: labels, descriptions, and aliases can be entered
  and displayed in every software-supported language, and the usual display
  language is the user's preferred language. [Help:Multilingual](https://www.wikidata.org/wiki/Help:Multilingual)
* A fallback chain is the systematic display mechanism used when content is not
  available in the primary language. Users can inspect their chain at
  `Special:MyLanguageFallbackChain`; ULS and Babel can configure one.
  [User options: language fallback chain](https://www.wikidata.org/wiki/Help:Navigating_Wikidata/User_Options#Language_fallback_chain)
* Item-page HTML titles/H1 headings and item-valued claims use **default**
  language fallback chains; `wbgetentities&languagefallback=1` does too.
  Special-page lists can use the user's configured chain.
  [User options](https://www.wikidata.org/wiki/Help:Navigating_Wikidata/User_Options#Language_fallback_chain)
* If no label exists in any language in the applicable chain, Wikidata lists
  show the identifier (for example, `Q…` or `P…`).
  [Help:Multilingual](https://www.wikidata.org/wiki/Help:Multilingual)
* Fallbacks are language-specific, not merely “requested language then
  English”: the `mul` documentation explicitly warns that some languages have
  non-trivial intermediate fallbacks before `mul` and `en`.
  [Default values](https://www.wikidata.org/wiki/Help:Default_values_for_labels_and_aliases)
* Thus a variant can fall back to a parent/base language (for example,
  `de-at` to `de`) where MediaWiki's configured fallback chain says so. The
  authoritative configuration concept is MediaWiki's per-language
  [fallback-language list](https://www.mediawiki.org/wiki/Manual:Language#Fallback_languages),
  rather than a universal string-truncation rule.
* English is a common final fallback in Wikidata examples and in the historical
  wording around `mul`, but it is not a substitute for the whole configurable
  chain. The recommended WDQS examples use `[AUTO_LANGUAGE],mul,en`.
  [SPARQL tutorial](https://www.wikidata.org/wiki/Wikidata:SPARQL_tutorial)

## Query/API behaviour is not automatically local-client behaviour

* `wbgetentities` can perform Wikibase language fallback when requested with
  `languagefallback=1`; a raw full labels map has not thereby been resolved.
  [User options](https://www.wikidata.org/wiki/Help:Navigating_Wikidata/User_Options#Language_fallback_chain)
* WDQS's `wikibase:label` service accepts one or more comma-separated language
  codes and considers them **in caller-supplied order**. If none matches, it
  returns the bare QID as the label. [WDQS user manual](https://www.mediawiki.org/wiki/Wikidata_Query_Service/User_Manual#Label_service)
* In WDQS, `[AUTO_LANGUAGE]` is replaced by the query UI user's interface
  language; for French, `[AUTO_LANGUAGE],en` becomes `fr,en`.
  [WDQS user manual](https://www.mediawiki.org/wiki/Wikidata_Query_Service/User_Manual#Label_service)
* Therefore a query's `"en"`, `"[AUTO_LANGUAGE],en"`, and
  `"[AUTO_LANGUAGE],mul,en"` are deliberately different policies. Since `mul`
  was added, Wikidata's own help says to amend the common query pattern to
  `[AUTO_LANGUAGE],mul,en`. [Default values](https://www.wikidata.org/wiki/Help:Default_values_for_labels_and_aliases)

## Guidance relevant to display

### Documented guidance

* The label guidance is a **proposed** policy/guideline, not a settled global
  policy. It says labels should be the most common name and labels in different
  languages may differ. [Help:Label](https://www.wikidata.org/wiki/Help:Label)
* When a label is missing in the user's languages, Wikidata's help says users
  may add a translation, but should make sure it is correct; otherwise the UI
  displays the identifier. [Help:Multilingual](https://www.wikidata.org/wiki/Help:Multilingual)
* The label guidance allows human transliteration/translation only under stated
  conditions and says to leave an uncertain non-proper-noun term for someone
  else. It does **not** endorse a tool inventing or machine-translating a label
  for display. [Help:Label](https://www.wikidata.org/wiki/Help:Label)

### Consequences

* Display a stored label verbatim; do not manufacture a translation, guessed
  transliteration, or a replacement label. This follows the documented guidance
  above and prevents a UI string being mistaken for Wikidata data.
* Showing a label from a non-requested language is normal fallback behaviour.
  For a CLI that chooses an arbitrary available language outside the official
  chain, showing its language tag makes that choice transparent. The tagging
  detail is this document's recommendation, not a quoted Wikidata rule.

## Recommendations for this project

These are **our recommendations**, derived from the sources above; they are not
claims about exact Wikidata UI parity.

1. Retain the full `labels` JSON map. Keep `en_label` only as an index/convenience
   field, never as the sole display source.
2. For the current English-oriented CLI, choose a deterministic display term in
   this order: `en` → `mul` → another available label. For the final case choose
   by normalized language code (lexicographic) and then value; do not depend on
   JSON/map iteration order.
3. Render provenance when the chosen code is not `en`: for example,
   `Landrat [de] (Q123)`, and render `mul` as `[mul/default]` or `[mul]` rather
   than pretending it is English. Always make the QID available, preferably in
   the same line/detail view.
4. If no labels exist, display the QID alone. This follows the documented UI and
   WDQS no-match convention.
5. If the tool later gets a user-selected language, implement an explicit
   policy: requested code; known configured parent/fallback codes; `mul`; `en`;
   deterministic any-language; QID. Do not claim it exactly matches Wikidata
   unless the tool obtains Wikibase's resolved fallback result/API behaviour.
6. Use `[AUTO_LANGUAGE],mul,en` (or a deliberately documented alternative) in
   future WDQS label-service queries. Do not expect a WDQS language list to be
   applied automatically to locally stored raw JSON.
7. Never write labels as a consequence of display fallback, and never
   machine-translate them. Missing labels are a data/editorial issue, not a
   reason to alter the position-review proposal workflow.
