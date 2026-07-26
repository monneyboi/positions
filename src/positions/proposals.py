"""Validation of the queue JSON payload the agent hands to `positions queue`.

A proposal is ONE entity plus an RFC 6902 JSON Patch that is submitted
verbatim to the Wikibase REST API (`PATCH /v1/entities/items/{id}`), plus
review metadata for the human. Validation here is structural only — op
names, JSON Pointers, required fields. Whether the patch is *wise* (pins,
ordering, choice of op) is agent guidance in the propose-edits skill, and
the server applies the patch atomically or not at all.

    {
      "proposals": [
        {
          "entity": "Q123",
          "patch": [
            {"op": "test", "path": "/statements/P39/2/id", "value": "Q123$…"},
            {"op": "replace", "path": "/statements/P39/2/rank", "value": "deprecated"},
            {"op": "add", "path": "/statements/P17/-", "value": {"property": …, …}}
          ],
          "comment": "deprecate wrong officeholder; add country Finland",
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

OPS = ("add", "remove", "replace", "move", "copy", "test")
EXISTING_STATE_OPS = ("remove", "replace", "move", "copy")


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


def _validate(item: object, i: int) -> dict:
    where = f"proposals[{i}]"
    if not isinstance(item, dict):
        raise PayloadError(f"{where}: expected an object")

    entity = str(item.get("entity", "")).strip().upper()
    if not _QID.match(entity):
        raise PayloadError(f"{where}.entity: expected an item QID, got {entity!r}")

    patch = _validate_patch(item.get("patch"), where)

    comment = item.get("comment")
    if not isinstance(comment, str) or not comment.strip():
        raise PayloadError(
            f"{where}.comment: required (becomes the Wikidata edit summary)"
        )

    rationale = item.get("rationale", "")
    if not isinstance(rationale, str):
        raise PayloadError(f"{where}.rationale: expected a string")
    rationale = rationale.strip()
    if not rationale and any(op["op"] in EXISTING_STATE_OPS for op in patch):
        raise PayloadError(
            f"{where}.rationale: required when the patch changes existing state"
        )

    sources = item.get("sources", [])
    if not isinstance(sources, list) or not all(isinstance(s, str) for s in sources):
        raise PayloadError(f"{where}.sources: expected a list of strings")

    return {
        "entity": entity,
        "patch": patch,
        "comment": comment.strip(),
        "rationale": rationale,
        "sources": sources,
    }
