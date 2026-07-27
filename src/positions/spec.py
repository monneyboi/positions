"""The Wikibase REST API operations an edit may use, derived from the OpenAPI spec.

A queued edit names one allowed `operationId` plus the `params` (path
parameters) and `body` (JSON request body) that operation declares. The
OpenAPI spec — not project code — defines method, path, parameter
patterns, and body fields; both validation (proposals.py) and submission
(wikidata.py) read them from the generated `data/operations.json`. The
only policy is ALLOWED: operations not listed cannot be queued. Notably
absent: `patchItem` (its positional statement paths can silently hit the
wrong statement when live order shifts) and `replaceItemStatement` /
`replaceStatement` (wholesale clobbering).

`data/operations.json` is a generated artifact, extracted from the live
spec (Wikidata's Stable Interface Policy covers v1). Refresh it — and
review the diff, which shows exactly what changed in the contract edits
rely on — with:

    uv run python -m positions.spec
"""

import json
import re
from functools import cache
from pathlib import Path
from typing import NamedTuple

DATA_PATH = Path(__file__).parent / "data" / "operations.json"
SPEC_URL = "https://www.wikidata.org/w/rest.php/wikibase/v1/openapi.json"
USER_AGENT = "positions/0.5 (personal Wikidata review tool; httpx)"

ALLOWED = (
    "addItem",
    "addItemStatement",
    "patchItemStatement",
    "deleteItemStatement",
    "replaceItemLabel",
    "deleteItemLabel",
    "replaceItemDescription",
    "deleteItemDescription",
    "addItemAliasesInLanguage",
)

#: Body fields every write operation accepts; never the point of an edit.
METADATA_FIELDS = frozenset({"tags", "bot", "comment"})

#: Params that take entity ids; a lowercase q/p prefix is normalized away.
ENTITY_PARAMS = ("item_id", "statement_id", "property_id")


class SpecError(Exception):
    """The generated operations data is missing or out of date."""


class Operation(NamedTuple):
    """One allowed REST operation, from the generated operations data."""

    method: str  # uppercase HTTP verb
    path: str  # "/v1/entities/items/{item_id}/..." (str.format template)
    path_params: dict[str, re.Pattern[str]]  # name -> spec validation pattern
    body_fields: frozenset[str]  # permitted body keys (incl. METADATA_FIELDS)
    body_required: frozenset[str]  # body keys the spec marks required


@cache
def operations() -> dict[str, Operation]:
    """The allowed operations, keyed by operationId."""
    raw = json.loads(DATA_PATH.read_text())
    missing = set(ALLOWED) - set(raw)
    if missing:
        raise SpecError(
            f"{DATA_PATH} is missing {sorted(missing)}; "
            "refresh it with `uv run python -m positions.spec`"
        )
    return {
        operation_id: Operation(
            method=entry["method"],
            path=entry["path"],
            path_params={k: re.compile(p) for k, p in entry["path_params"].items()},
            body_fields=frozenset(entry["body_fields"]),
            body_required=frozenset(entry["body_required"]),
        )
        for operation_id, entry in raw.items()
    }


def _extract(document: dict) -> dict:
    """The slim shape of every allowed operation in a full OpenAPI document."""
    found = {}
    for path, methods in document["paths"].items():
        for method, op in methods.items():
            operation_id = op.get("operationId")
            if operation_id not in ALLOWED:
                continue
            fields: set[str] = set()
            required: set[str] = set()
            content = op.get("requestBody", {}).get("content", {})
            schema = content.get("application/json", {}).get("schema", {})
            for part in schema.get("allOf", [schema]):  # payload + tags/bot/comment
                fields.update(part.get("properties", ()))
                required.update(part.get("required", ()))
            found[operation_id] = {
                "method": method.upper(),
                "path": path,
                "path_params": {
                    p["name"]: p.get("schema", {}).get("pattern", r"^\S+$")
                    for p in op.get("parameters", [])
                    if p["in"] == "path"
                },
                "body_fields": sorted(fields),
                "body_required": sorted(required),
            }
    missing = set(ALLOWED) - set(found)
    if missing:
        raise SpecError(
            f"allowed operations not found in the live spec: {sorted(missing)}"
        )
    return {operation_id: found[operation_id] for operation_id in sorted(found)}


def refresh() -> None:
    """Fetch the live OpenAPI spec and regenerate data/operations.json."""
    import httpx

    document = (
        httpx.get(SPEC_URL, headers={"User-Agent": USER_AGENT}, timeout=60.0)
        .raise_for_status()
        .json()
    )
    extracted = _extract(document)
    DATA_PATH.write_text(json.dumps(extracted, indent=1) + "\n")
    print(f"wrote {DATA_PATH} ({len(extracted)} operations)")


if __name__ == "__main__":
    refresh()
