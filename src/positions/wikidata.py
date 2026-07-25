"""Wikidata entity API client (wbgetentities batches) and authenticated edits."""

import json
import os
import time
from collections.abc import Callable, Iterable

import httpx

API_URL = "https://www.wikidata.org/w/api.php"
USER_AGENT = "positions/0.1 (personal Wikidata audit tool; httpx)"

BATCH_SIZE = 50  # wbgetentities max

# Item-valued and time-valued claims we keep locally. Broad on purpose:
# the local model should support checks we haven't thought of yet.
KEEP_CLAIMS = {
    # classification
    "P31",  # instance of
    "P279",  # subclass of
    # jurisdiction / structure
    "P17",  # country
    "P1001",  # applies to jurisdiction
    "P361",  # part of
    "P527",  # has part(s)
    "P749",  # parent organization
    "P2389",  # organization directed by the office or position
    # lifecycle
    "P571",  # inception
    "P576",  # dissolved/abolished
    "P1365",  # replaces
    "P1366",  # replaced by
    # holders & government
    "P1308",  # position holder
    "P6",  # head of government
    "P35",  # head of state
    "P194",  # legislative body
    # govdirectory
    "P9798",  # COFOG
    "P856",  # official website
    # meta
    "P910",  # topic's main category
    "P6104",  # maintained by WikiProject
}


def _qid_of(claim: dict) -> str | None:
    datavalue = claim["mainsnak"].get("datavalue")
    if datavalue is None or datavalue["type"] != "wikibase-entityid":
        return None
    return datavalue["value"]["id"]


def _time_of(claim: dict) -> str | None:
    datavalue = claim["mainsnak"].get("datavalue")
    if datavalue is None or datavalue["type"] != "time":
        return None
    return datavalue["value"]["time"]


def parse_claims(entity: dict) -> list[tuple[str, str, str, str, str]]:
    """Normalize the allowlisted, non-deprecated claims of an API entity."""
    parsed = []
    for prop, prop_claims in entity.get("claims", {}).items():
        if prop not in KEEP_CLAIMS:
            continue
        for claim in prop_claims:
            rank = claim["rank"]
            if rank == "deprecated":
                continue
            statement_id = claim["id"]
            if (qid := _qid_of(claim)) is not None:
                parsed.append((prop, qid, "item", rank, statement_id))
            elif (time_value := _time_of(claim)) is not None:
                parsed.append((prop, time_value, "time", rank, statement_id))
    return parsed


def parse_entity(entity: dict) -> dict:
    """Extract the locally useful parts of a wbgetentities entity."""
    labels = {lang: l["value"] for lang, l in entity.get("labels", {}).items()}
    descriptions = {
        lang: d["value"] for lang, d in entity.get("descriptions", {}).items()
    }
    aliases = {
        lang: [a["value"] for a in als]
        for lang, als in entity.get("aliases", {}).items()
    }
    return {
        "qid": entity["id"],
        "lastrevid": entity["lastrevid"],
        "labels": labels,
        "descriptions": descriptions,
        "aliases": aliases,
        "claims": parse_claims(entity),
    }


def fetch_entities(
    qids: Iterable[str],
    batch_size: int = BATCH_SIZE,
    on_retry: Callable[[str], None] | None = None,
):
    """Yield parsed entities for qids, in wbgetentities batches."""
    batch: list[str] = []
    with httpx.Client(
        timeout=60.0, headers={"User-Agent": USER_AGENT}, follow_redirects=True
    ) as client:
        for qid in qids:
            batch.append(qid)
            if len(batch) >= batch_size:
                yield from _fetch_batch(client, batch, on_retry=on_retry)
                batch = []
        if batch:
            yield from _fetch_batch(client, batch, on_retry=on_retry)


def _fetch_batch(
    client: httpx.Client,
    batch: list[str],
    retries: int = 5,
    on_retry: Callable[[str], None] | None = None,
):
    for attempt in range(retries):
        try:
            resp = client.get(
                API_URL,
                params={
                    "action": "wbgetentities",
                    "ids": "|".join(batch),
                    "props": "info|labels|descriptions|aliases|claims",
                    "format": "json",
                    "formatversion": "2",
                },
            )
            if resp.status_code in (429, 500, 502, 503, 504):
                raise httpx.HTTPError(f"HTTP {resp.status_code}")
            resp.raise_for_status()
            entities = resp.json()["entities"]
            for entity in entities.values():
                if "missing" not in entity:
                    yield parse_entity(entity)
            return
        except httpx.HTTPError as e:
            wait = min(2**attempt * 2, 60)
            if on_retry is not None:
                on_retry(
                    f"Wikidata API batch {batch[0]}: request "
                    f"{attempt + 1}/{retries} failed ({e}); retrying in {wait}s"
                )
            time.sleep(wait)
    raise RuntimeError(f"wbgetentities failed for batch starting {batch[0]}")


# ---------------------------------------------------------------------------
# Authenticated live checks and edits (review loop "accept" path)
# ---------------------------------------------------------------------------
#
# The local model only exists to produce candidates. Before anything is
# submitted we re-fetch the live entity and verify the preconditions still
# hold, then edit with baserevid for optimistic concurrency. The edit
# response carries the new statement IDs and the new lastrevid, which we
# write back into the local model so no re-import is needed.


class SubmitError(Exception):
    """A Wikidata edit was rejected or failed; safe to retry manually."""


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


def fetch_live(client: httpx.Client, qid: str) -> dict:
    """Fetch the raw live entity (info + ALL claims, deprecated included).

    Unlike the sync parser, nothing is filtered: the review safeguard must
    see statements at every rank before deciding an edit is still valid.
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


def claim_item_value(claim: dict) -> str | None:
    """Return the item QID of a value snak, or None for another snak type."""
    return _qid_of(claim)


def non_deprecated_values(entity: dict, prop: str) -> list[str]:
    """Live item values of a property, excluding deprecated statements."""
    return [
        qid
        for claim in entity.get("claims", {}).get(prop, [])
        if claim.get("rank") != "deprecated"
        and (qid := claim_item_value(claim)) is not None
    ]


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
    property_values: dict[str, str],
    baserevid: int,
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
                "property": prop,
                "datavalue": {
                    "value": {"entity-type": "item", "numeric-id": int(value[1:])},
                    "type": "wikibase-entityid",
                },
            },
            "type": "statement",
            "rank": "normal",
        }
        for prop, value in property_values.items()
    ]
    params = {
        "action": "wbeditentity",
        "id": qid,
        "data": json.dumps({"claims": claims}),
        "baserevid": str(baserevid),
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
