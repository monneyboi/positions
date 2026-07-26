"""Validation of the queue JSON payload the agent hands to `positions queue`.

The format is a slimmed-down Wikidata statement shape: add-only, item-valued
statements. One proposal edits one entity and is submitted atomically.

    {
      "proposals": [
        {
          "entity": "Q123",
          "statements": [{"property": "P17", "value": "Q33"}],
          "summary": "add country (P17) Finland to Minister of X",
          "rationale": "why this is correct",
          "sources": ["https://..."]
        }
      ]
    }

A bare JSON list of proposals is also accepted.
"""

import json
import re

_QID = re.compile(r"^Q[1-9]\d*$")
_PID = re.compile(r"^P[1-9]\d*$")


class PayloadError(Exception):
    """The queue payload is malformed; nothing was enqueued."""


def load(text: str) -> list[dict]:
    """Parse and validate queue JSON, returning normalized proposal dicts."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise PayloadError(f"invalid JSON: {error}") from error
    if isinstance(data, dict):
        data = data.get("proposals")
    if not isinstance(data, list):
        raise PayloadError('expected a JSON list or {"proposals": [...]}')
    return [_validate(item, i) for i, item in enumerate(data)]


def _validate(item: object, i: int) -> dict:
    where = f"proposals[{i}]"
    if not isinstance(item, dict):
        raise PayloadError(f"{where}: expected an object")

    entity = str(item.get("entity", "")).strip().upper()
    if not _QID.match(entity):
        raise PayloadError(f"{where}.entity: expected an item QID, got {entity!r}")

    raw_statements = item.get("statements")
    if not isinstance(raw_statements, list) or not raw_statements:
        raise PayloadError(f"{where}.statements: expected a non-empty list")
    statements = []
    for j, st in enumerate(raw_statements):
        if not isinstance(st, dict):
            raise PayloadError(f"{where}.statements[{j}]: expected an object")
        prop = str(st.get("property", "")).strip().upper()
        value = str(st.get("value", "")).strip().upper()
        if not _PID.match(prop):
            raise PayloadError(
                f"{where}.statements[{j}].property: expected a PID, got {prop!r}"
            )
        if not _QID.match(value):
            raise PayloadError(
                f"{where}.statements[{j}].value: "
                f"expected an item QID, got {value!r} "
                "(only item-valued statements are supported)"
            )
        statements.append({"property": prop, "value": value})

    summary = item.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise PayloadError(f"{where}.summary: required (human-readable edit summary)")

    rationale = item.get("rationale", "")
    if not isinstance(rationale, str):
        raise PayloadError(f"{where}.rationale: expected a string")

    sources = item.get("sources", [])
    if not isinstance(sources, list) or not all(isinstance(s, str) for s in sources):
        raise PayloadError(f"{where}.sources: expected a list of strings")

    return {
        "entity": entity,
        "statements": statements,
        "summary": summary.strip(),
        "rationale": rationale.strip(),
        "sources": sources,
    }
