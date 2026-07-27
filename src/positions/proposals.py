"""Validation of the queue JSON payload the agent hands to `positions queue`.

The payload is ONE batch or a list of batches. A batch is one rationale
plus a non-empty list of edits — the human reviews and decides the batch
as a unit. An edit is one Wikibase REST API operation, named by its
`operationId` from the allowed operations (spec.py filters the OpenAPI
spec down to them) and carrying the
`params` (path parameters) and `body` (request body) that operation
declares — submitted verbatim, atomically or not at all:

    {
      "rationale": "why these edits are correct — what the human verifies",
      "edits": [
        {
          "operationId": "patchItemStatement",
          "params": {"item_id": "Q123", "statement_id": "Q123$1B7C…"},
          "body": {"patch": [
            {"op": "replace", "path": "/rank", "value": "deprecated"},
            {"op": "add", "path": "/qualifiers/-", "value": {…}}
          ]}
        },
        {
          "operationId": "addItem",
          "body": {"item": {
            "labels": {"en": "Minister of Finance of Finland"},
            "statements": {"P31": [{…}]}
          }}
        }
      ]
    }

The rationale is the only queue metadata: it is what the human verifies
against, shared by every edit in the batch; sourcing lives in the payload
itself (statement references). Validation here is structural only and
read from the spec: the operation is on the allowlist, the params are
exactly its path parameters and match their patterns, the body carries
its declared fields. Whether a payload is *wise* (deprecate-vs-remove,
references on added statements, existence checks before creates) is agent
guidance in the propose-edits skill. A bare JSON list of batch objects is
also accepted.
"""

import json
import re

from . import spec


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


def _validate_params(params: object, patterns: dict[str, str], where: str) -> dict:
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise PayloadError(f"{where}.params: expected an object")
    if set(params) != set(patterns):
        raise PayloadError(
            f"{where}.params: expected exactly {sorted(patterns)}, got {sorted(params)}"
        )
    normalized = {}
    for name, value in params.items():
        if not isinstance(value, str) or not re.match(patterns[name], value):
            raise PayloadError(
                f"{where}.params.{name}: {value!r} does not match {patterns[name]}"
            )
        if name in spec.ENTITY_PARAMS and value[:1] in ("q", "p"):
            value = value[0].upper() + value[1:]
        normalized[name] = value
    return normalized


def _validate_body(body: object, op: dict, where: str) -> dict | None:
    fields, required = spec.body_shape(op)
    payload_fields = fields - spec.METADATA_FIELDS
    if body is None:
        if payload_fields or required:
            raise PayloadError(
                f"{where}.body: required, with at least one of {sorted(payload_fields)}"
            )
        return None
    if not isinstance(body, dict) or not body:
        raise PayloadError(f"{where}.body: expected a non-empty object")
    unknown = set(body) - fields
    if unknown:
        raise PayloadError(f"{where}.body: unexpected fields {sorted(unknown)}")
    missing = required - set(body)
    if missing:
        raise PayloadError(f"{where}.body: missing required fields {sorted(missing)}")
    if payload_fields and not (set(body) - spec.METADATA_FIELDS):
        raise PayloadError(
            f"{where}.body: expected at least one of {sorted(payload_fields)}"
        )
    return body


def _validate_edit(edit: object, where: str) -> dict:
    if not isinstance(edit, dict):
        raise PayloadError(f"{where}: expected an object")
    unknown = set(edit) - {"operationId", "params", "body"}
    if unknown:
        raise PayloadError(f"{where}: unexpected fields {sorted(unknown)}")

    operation_id = edit.get("operationId")
    if not isinstance(operation_id, str) or operation_id not in spec.ALLOWED:
        raise PayloadError(
            f"{where}.operationId: expected one of {list(spec.ALLOWED)}, "
            f"got {operation_id!r}"
        )
    _, _, op = spec.lookup(operation_id)
    return {
        "operationId": operation_id,
        "params": _validate_params(edit.get("params"), spec.path_patterns(op), where),
        "body": _validate_body(edit.get("body"), op, where),
    }


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
