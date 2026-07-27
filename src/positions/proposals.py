"""Validation of the queue JSON payload the agent hands to `positions queue`.

The payload is ONE batch or a list of batches. A batch is one rationale
plus a non-empty list of edits — the human reviews and decides the batch
as a unit. An edit is one of two kinds, each submitted verbatim to the
Wikibase REST API — atomically or not at all:

- "patch":  one entity QID plus an RFC 6902 JSON Patch, sent to
  `PATCH /v1/entities/items/{id}`
- "create": one new-item document, sent to `POST /v1/entities/items`

The rationale is the only metadata: it is what the human verifies
against, shared by every edit in the batch. Validation here is
structural only — kinds, required fields, op names, JSON Pointers, item
sections. Whether a payload is *wise* (test pins, deprecate-vs-remove,
references on added statements, is the item really missing) is agent
guidance in the propose-edits skill.

    {
      "rationale": "why these edits are correct — what the human verifies",
      "edits": [
        {
          "kind": "patch",
          "entity": "Q123",
          "patch": [
            {"op": "test", "path": "/statements/P39/2/id", "value": "Q123$…"},
            {"op": "replace", "path": "/statements/P39/2/rank", "value": "deprecated"}
          ]
        },
        {
          "kind": "create",
          "item": {
            "labels": {"en": "Minister of Finance of Finland"},
            "statements": {"P31": [{"property": {"id": "P31"}, "value": …}]}
          }
        }
      ]
    }

A bare JSON list of batch objects is also accepted.
"""

import json
import re

_QID = re.compile(r"^Q[1-9]\d*$")

PATCH = "patch"
CREATE = "create"
KINDS = (PATCH, CREATE)

OPS = ("add", "remove", "replace", "move", "copy", "test")
ITEM_SECTIONS = ("labels", "descriptions", "aliases", "statements", "sitelinks")


class PayloadError(Exception):
    """The queue payload is malformed; nothing was enqueued."""


def load(text: str) -> list[dict]:
    """Parse and validate queue JSON, returning normalized batch dicts."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise PayloadError(f"invalid JSON: {error}") from error
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise PayloadError("expected a batch object or a list of batch objects")
    return [_validate_batch(item, i) for i, item in enumerate(data)]


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


def _validate_edit(edit: object, where: str) -> dict:
    if not isinstance(edit, dict):
        raise PayloadError(f"{where}: expected an object")

    kind = edit.get("kind")
    if kind not in KINDS:
        raise PayloadError(f"{where}.kind: expected one of {list(KINDS)}, got {kind!r}")

    if kind == PATCH:
        if "item" in edit:
            raise PayloadError(f"{where}: a patch edit has no 'item'")
        entity = str(edit.get("entity", "")).strip().upper()
        if not _QID.match(entity):
            raise PayloadError(f"{where}.entity: expected an item QID, got {entity!r}")
        patch = _validate_patch(edit.get("patch"), where)
        return {"kind": PATCH, "entity": entity, "payload": patch}

    if "entity" in edit or "patch" in edit:
        raise PayloadError(
            f"{where}: a create has neither 'entity' nor 'patch' — "
            "the QID is assigned on creation"
        )
    return {"kind": CREATE, "entity": None, "payload": _validate_item(edit.get("item"), where)}


def _validate_batch(item: object, i: int) -> dict:
    where = f"batches[{i}]"
    if not isinstance(item, dict):
        raise PayloadError(f"{where}: expected an object")

    rationale = item.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        raise PayloadError(
            f"{where}.rationale: required (what the human verifies against)"
        )

    edits = item.get("edits")
    if not isinstance(edits, list) or not edits:
        raise PayloadError(f"{where}.edits: expected a non-empty list")

    return {
        "rationale": rationale.strip(),
        "edits": [
            _validate_edit(edit, f"{where}.edits[{j}]") for j, edit in enumerate(edits)
        ],
    }
