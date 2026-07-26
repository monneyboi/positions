"""Wikidata live checks and authenticated edits (the review "accept" path).

Nothing here mirrors or caches Wikidata. Immediately before a proposal is
submitted we re-fetch the live entity, confirm the proposed statements are
still new, and edit with baserevid for optimistic concurrency.
"""

import json
import os
import time

import httpx

API_URL = "https://www.wikidata.org/w/api.php"
USER_AGENT = "positions/0.2 (personal Wikidata review tool; httpx)"


class SubmitError(Exception):
    """A Wikidata edit was rejected or failed; safe to retry manually."""


class SubmitConflict(Exception):
    """Live Wikidata state disagrees with the queued proposal."""


def access_token() -> str | None:
    return os.environ.get("WIKIDATA_ACCESS_TOKEN")


def _auth_client() -> httpx.Client:
    token = access_token()
    if not token:
        raise SubmitError("WIKIDATA_ACCESS_TOKEN is not set (see .env.example)")
    return httpx.Client(
        timeout=60.0,
        headers={"User-Agent": USER_AGENT, "Authorization": f"Bearer {token}"},
        follow_redirects=True,
    )


def _qid_of(claim: dict) -> str | None:
    datavalue = claim["mainsnak"].get("datavalue")
    if datavalue is None or datavalue["type"] != "wikibase-entityid":
        return None
    return datavalue["value"]["id"]


def claim_item_value(claim: dict) -> str | None:
    """Return the item QID of a value snak, or None for another snak type."""
    return _qid_of(claim)


def fetch_live(client: httpx.Client, qid: str) -> dict:
    """Fetch the raw live entity (info + ALL claims, deprecated included).

    Nothing is filtered: the review safeguard must see statements at every
    rank before deciding an edit is still valid.
    """
    try:
        resp = client.get(
            API_URL,
            params={
                "action": "wbgetentities",
                "ids": qid,
                "props": "info|claims",
                "format": "json",
                "formatversion": "2",
            },
        )
        resp.raise_for_status()
    except httpx.HTTPError as error:
        raise SubmitError(f"could not fetch live {qid}: {error}") from error
    entity = resp.json()["entities"][qid]
    if "missing" in entity:
        raise SubmitError(f"{qid} no longer exists on Wikidata")
    return entity


def non_deprecated_values(entity: dict, prop: str) -> list[str]:
    """Live item values of a property, excluding deprecated statements."""
    return [
        qid
        for claim in entity.get("claims", {}).get(prop, [])
        if claim.get("rank") != "deprecated"
        and (qid := claim_item_value(claim)) is not None
    ]


def verify_live(client: httpx.Client, entity: str, statements: list[dict]) -> int:
    """Confirm every proposed statement is still new; return the base revision.

    This is the last automated guard before an edit: the human reviewed a
    proposal, and here we only check that live Wikidata has not gained the
    same statement (at a non-deprecated rank) in the meantime.
    """
    live = fetch_live(client, entity)
    for statement in statements:
        prop, value = statement["property"], statement["value"]
        existing = non_deprecated_values(live, prop)
        if value in existing:
            raise SubmitConflict(
                f"{entity} already has {prop} → {value} — someone got there first"
            )
    return live["lastrevid"]


def _csrf_token(client: httpx.Client) -> str:
    try:
        resp = client.get(
            API_URL,
            params={
                "action": "query",
                "meta": "tokens",
                "type": "csrf",
                "format": "json",
            },
        )
        resp.raise_for_status()
    except httpx.HTTPError as error:
        raise SubmitError(f"could not fetch a CSRF token: {error}") from error
    return resp.json()["query"]["tokens"]["csrftoken"]


def add_item_claims(
    client: httpx.Client,
    qid: str,
    statements: list[dict],
    baserevid: int,
    summary: str,
    retries: int = 3,
) -> dict:
    """Add item-valued claims in ONE atomic wbeditentity edit.

    `baserevid` is the lastrevid of the live entity we just checked, so the
    edit fails with an edit conflict instead of silently overwriting someone
    else's change. Returns the response entity (new claim IDs + lastrevid).
    """
    claims = [
        {
            "mainsnak": {
                "snaktype": "value",
                "property": statement["property"],
                "datavalue": {
                    "value": {
                        "entity-type": "item",
                        "numeric-id": int(statement["value"][1:]),
                    },
                    "type": "wikibase-entityid",
                },
            },
            "type": "statement",
            "rank": "normal",
        }
        for statement in statements
    ]
    params = {
        "action": "wbeditentity",
        "id": qid,
        "data": json.dumps({"claims": claims}),
        "baserevid": str(baserevid),
        "summary": summary,
        "maxlag": "5",
        "format": "json",
        "token": _csrf_token(client),
    }
    for attempt in range(retries):
        try:
            resp = client.post(API_URL, data=params)
            if resp.status_code in (429, 500, 502, 503, 504):
                time.sleep(min(2**attempt * 5, 60))
                continue
            resp.raise_for_status()
        except httpx.HTTPError as error:
            if attempt + 1 == retries:
                raise SubmitError(f"Wikidata edit request failed: {error}") from error
            time.sleep(min(2**attempt * 5, 60))
            continue
        data = resp.json()
        if "error" in data:
            info = data["error"].get("info", data["error"].get("code", "unknown"))
            raise SubmitError(f"Wikidata rejected the edit: {info}")
        return data["entity"]
    raise SubmitError(f"Wikidata edit failed after {retries} attempts (server busy)")
