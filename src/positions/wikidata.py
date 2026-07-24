"""Wikidata entity API client (wbgetentities batches)."""

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
    try:
        dv = claim["mainsnak"]["datavalue"]
        if dv["type"] == "wikibase-entityid":
            return "Q" + str(dv["value"]["numeric-id"])
    except (KeyError, TypeError):
        pass
    return None


def _time_of(claim: dict) -> str | None:
    try:
        dv = claim["mainsnak"]["datavalue"]
        if dv["type"] == "time":
            return dv["value"]["time"]
    except (KeyError, TypeError):
        pass
    return None


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
    claims = []
    for prop, prop_claims in entity.get("claims", {}).items():
        if prop not in KEEP_CLAIMS:
            continue
        for claim in prop_claims:
            rank = claim.get("rank", "normal")
            if rank == "deprecated":
                continue
            qid = _qid_of(claim)
            if qid is not None:
                claims.append((prop, qid, "item", rank))
                continue
            t = _time_of(claim)
            if t is not None:
                claims.append((prop, t, "time", rank))
    return {
        "qid": entity["id"],
        "lastrevid": entity["lastrevid"],
        "labels": labels,
        "descriptions": descriptions,
        "aliases": aliases,
        "claims": claims,
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
            data = resp.json()
            entities = data.get("entities", {})
            if isinstance(entities, dict):
                entities = entities.values()
            for entity in entities:
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
