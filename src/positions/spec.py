"""The Wikibase REST API operations an edit may use: a filtered OpenAPI spec.

A queued edit names one allowed `operationId` plus the `params` (path
parameters) and `body` (JSON request body) that operation declares. The
OpenAPI spec — not project code — defines method, path, parameter
patterns, and body fields: `data/operations.json` is the live spec with
every operation outside ALLOWED removed, otherwise verbatim, and both
validation (proposals.py) and submission (wikidata.py) read straight
from it. ALLOWED is the only policy. Notably absent: `patchItem` (its
positional statement paths can silently hit the wrong statement when
live order shifts) and `replaceItemStatement` / `replaceStatement`
(wholesale clobbering).

Refresh (Wikidata's Stable Interface Policy covers v1) — the diff shows
exactly what changed in the contract edits rely on:

    uv run python -m positions.spec
"""

import json
from functools import cache
from pathlib import Path

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
    """The operations data is missing allowed operations; refresh it."""


@cache
def _operations() -> dict[str, tuple[str, str, dict]]:
    """Every operation in the data file: operationId -> (method, path, spec op)."""
    document = json.loads(DATA_PATH.read_text())
    index = {
        op["operationId"]: (method, path, op)
        for path, methods in document["paths"].items()
        for method, op in methods.items()
    }
    missing = set(ALLOWED) - set(index)
    if missing:
        raise SpecError(
            f"{DATA_PATH} is missing {sorted(missing)}; "
            "refresh it with `uv run python -m positions.spec`"
        )
    return index


def lookup(operation_id: str) -> tuple[str, str, dict]:
    """The operation's HTTP method, path template, and verbatim spec entry."""
    return _operations()[operation_id]


def path_patterns(op: dict) -> dict[str, str]:
    """The operation's path parameters and their spec validation patterns."""
    return {
        p["name"]: p.get("schema", {}).get("pattern", r"^\S+$")
        for p in op.get("parameters", [])
        if p["in"] == "path"
    }


def body_shape(op: dict) -> tuple[frozenset[str], frozenset[str]]:
    """Permitted and required body fields (the spec's allOf: payload + metadata)."""
    fields: set[str] = set()
    required: set[str] = set()
    content = op.get("requestBody", {}).get("content", {})
    schema = content.get("application/json", {}).get("schema", {})
    for part in schema.get("allOf", [schema]):
        fields.update(part.get("properties", ()))
        required.update(part.get("required", ()))
    return frozenset(fields), frozenset(required)


def refresh() -> None:
    """Fetch the live OpenAPI spec and regenerate data/operations.json."""
    import httpx

    document = (
        httpx.get(SPEC_URL, headers={"User-Agent": USER_AGENT}, timeout=60.0)
        .raise_for_status()
        .json()
    )
    paths = {}
    for path, methods in document["paths"].items():
        kept = {
            method: op
            for method, op in methods.items()
            if op.get("operationId") in ALLOWED
        }
        if kept:
            paths[path] = kept
    found = {op["operationId"] for methods in paths.values() for op in methods.values()}
    missing = set(ALLOWED) - found
    if missing:
        raise SpecError(
            f"allowed operations not found in the live spec: {sorted(missing)}"
        )
    DATA_PATH.write_text(json.dumps({"paths": paths}, indent=1) + "\n")
    print(f"wrote {DATA_PATH} ({len(found)} operations)")


if __name__ == "__main__":
    refresh()
