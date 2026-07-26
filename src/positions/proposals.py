"""Validation of the queue JSON payload the agent hands to `positions queue`.

A proposal is ONE of two kinds, each submitted verbatim to the Wikibase
REST API — atomically or not at all:

- "patch":  one entity QID plus an RFC 6902 JSON Patch, sent to
  `PATCH /v1/entities/items/{id}`
- "create": one new-item document, sent to `POST /v1/entities/items`

plus review metadata for the human. Validation here is structural only —
kinds, required fields, op names, JSON Pointers, item sections. Whether a
payload is *wise* (test pins, deprecate-vs-remove, is the item really
missing) is agent guidance in the propose-edits skill.

    {
      "proposals": [
        {
          "kind": "patch",
          "entity": "Q123",
          "patch": [
            {"op": "test", "path": "/statements/P39/2/id", "value": "Q123$…"},
            {"op": "replace", "path": "/statements/P39/2/rank", "value": "deprecated"}
          ],
          "comment": "deprecate wrong officeholder",
          "rationale": "why this is correct",
          "sources": ["https://..."]
        },
        {
          "kind": "create",
          "item": {
            "labels": {"en": "Minister of Finance of Finland"},
            "statements": {"P31": [{"property": {"id": "P31"}, "value": …}]}
          },
          "comment": "create Minister of Finance of Finland",
          "rationale": "why this item is missing and needed",
          "sources": ["https://..."]
        }
      ]
    }

A bare JSON list of proposals is also accepted.
"""

import json
import re

_QID = re.compile(r"^Q[1-9]\d*$")

PATCH = "patch"
CREATE = "create"
KINDS = (PATCH, CREATE)

OPS = ("add", "remove", "replace", "move", "copy", "test")
EXISTING_STATE_OPS = ("remove", "replace", "move", "copy")
ITEM_SECTIONS = ("labels", "descriptions", "aliases", "statements", "sitelinks")


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


def _pointer(value: object) -> str | None:
    """The value as a JSON Pointer, or None if it isn't a valid one."""
    if isinstance(value, str) and (value == "" or value.startswith("/")):
        return value
    return None


def _validate_patch(patch: object, where: str) -> list[dict]:
    if not isinstance(patch, list) or not patch:
        raise PayloadError(f"{where}.patch: expected a non-empty list of ops")
    for j, op in enumerate(patch):
        op_where = f"{where}.patch[{j}]"
        if not isinstance(op, dict):
            raise PayloadError(f"{op_where}: expected an object")
        name = op.get("op")
        if name not in OPS:
            raise PayloadError(
                f"{op_where}.op: expected one of {list(OPS)}, got {name!r}"
            )
        if _pointer(op.get("path")) is None:
            raise PayloadError(
                f"{op_where}.path: expected a JSON Pointer, got {op.get('path')!r}"
            )
        if name in ("add", "replace", "test") and "value" not in op:
            raise PayloadError(f"{op_where}: {name!r} requires a value")
        if name in ("move", "copy") and _pointer(op.get("from")) is None:
            raise PayloadError(
                f"{op_where}.from: expected a JSON Pointer, got {op.get('from')!r}"
            )
    return patch


def _validate_item(document: object, where: str) -> dict:
    if not isinstance(document, dict) or not document:
        raise PayloadError(f"{where}.item: expected a non-empty item object")
    for section, content in document.items():
        if not isinstance(content, dict):
            raise PayloadError(f"{where}.item.{section}: expected an object")
    if not any(document.get(section) for section in ITEM_SECTIONS):
        raise PayloadError(
            f"{where}.item: expected at least one of {list(ITEM_SECTIONS)}"
        )
    return document


def _validate(item: object, i: int) -> dict:
    where = f"proposals[{i}]"
    if not isinstance(item, dict):
        raise PayloadError(f"{where}: expected an object")

    kind = item.get("kind")
    if kind not in KINDS:
        raise PayloadError(f"{where}.kind: expected one of {list(KINDS)}, got {kind!r}")

    comment = item.get("comment")
    if not isinstance(comment, str) or not comment.strip():
        raise PayloadError(
            f"{where}.comment: required (becomes the Wikidata edit summary)"
        )

    rationale = item.get("rationale", "")
    if not isinstance(rationale, str):
        raise PayloadError(f"{where}.rationale: expected a string")
    rationale = rationale.strip()

    sources = item.get("sources", [])
    if not isinstance(sources, list) or not all(isinstance(s, str) for s in sources):
        raise PayloadError(f"{where}.sources: expected a list of strings")

    base = {
        "kind": kind,
        "comment": comment.strip(),
        "rationale": rationale,
        "sources": sources,
    }

    if kind == PATCH:
        if "item" in item:
            raise PayloadError(f"{where}: a patch proposal has no 'item'")
        entity = str(item.get("entity", "")).strip().upper()
        if not _QID.match(entity):
            raise PayloadError(f"{where}.entity: expected an item QID, got {entity!r}")
        patch = _validate_patch(item.get("patch"), where)
        if not rationale and any(op["op"] in EXISTING_STATE_OPS for op in patch):
            raise PayloadError(
                f"{where}.rationale: required when the patch changes existing state"
            )
        return {**base, "entity": entity, "payload": patch}

    if "entity" in item or "patch" in item:
        raise PayloadError(
            f"{where}: a create has neither 'entity' nor 'patch' — "
            "the QID is assigned on creation"
        )
    if not rationale:
        raise PayloadError(
            f"{where}.rationale: required for a create (why is this item missing?)"
        )
    return {**base, "entity": None, "payload": _validate_item(item.get("item"), where)}
