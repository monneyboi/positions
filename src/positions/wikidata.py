"""Authenticated submission to the Wikibase REST API (the review "accept" path).

A proposal's JSON Patch is self-verifying: its `test` ops pin the live
state the patch mutates, and the server evaluates the whole patch
atomically. So there is no client-side pre-flight check — we POST the
patch verbatim and map the response onto the queue's outcomes:

- 200          → submitted (new revision id from the response ETag)
- 404/409/412  → the pinned live state changed; the proposal is stale
- anything else → failed (the proposal stays pending for a human decision)
"""

import os
import time

import httpx

API_URL = "https://www.wikidata.org/w/rest.php/wikibase/v1"
USER_AGENT = "positions/0.3 (personal Wikidata review tool; httpx)"

RETRIES = 3  # PATCH attempts on transient server errors
RETRYABLE = (429, 500, 502, 503, 504)
STALE_CODES = (404, 409, 412)  # item gone, or a test pin no longer holds


class SubmitError(Exception):
    """A Wikidata edit was rejected or failed; safe to retry manually."""


class SubmitConflict(Exception):
    """Live Wikidata state disagrees with the queued patch (stale)."""


def auth_client() -> httpx.Client:
    token = os.environ.get("WIKIDATA_ACCESS_TOKEN")
    if not token:
        raise SubmitError("WIKIDATA_ACCESS_TOKEN is not set (see .env.example)")
    return httpx.Client(
        timeout=60.0,
        headers={"User-Agent": USER_AGENT, "Authorization": f"Bearer {token}"},
        follow_redirects=True,
    )


def _message(resp: httpx.Response) -> str:
    try:
        return str(resp.json().get("message", "")) or resp.text[:200]
    except ValueError:
        return resp.text[:200]


def _revision_id(resp: httpx.Response) -> int | None:
    etag = resp.headers.get("ETag", "").strip('"')
    return int(etag) if etag.isdigit() else None


def submit_patch(
    client: httpx.Client, qid: str, patch: list[dict], comment: str
) -> int | None:
    """Submit the patch verbatim; return the new revision id on success."""
    url = f"{API_URL}/entities/items/{qid}"
    body = {"patch": patch, "comment": comment}
    for attempt in range(RETRIES):
        try:
            resp = client.patch(url, json=body)
        except httpx.HTTPError as error:
            if attempt + 1 == RETRIES:
                raise SubmitError(f"Wikidata edit request failed: {error}") from error
            time.sleep(min(2**attempt * 5, 60))
            continue
        if resp.status_code == 200:
            return _revision_id(resp)
        if resp.status_code in STALE_CODES:
            raise SubmitConflict(_message(resp))
        if resp.status_code in RETRYABLE and attempt + 1 < RETRIES:
            time.sleep(min(2**attempt * 5, 60))
            continue
        raise SubmitError(
            f"Wikidata rejected the edit ({resp.status_code}): {_message(resp)}"
        )
    raise SubmitError(f"Wikidata edit failed after {RETRIES} attempts (server busy)")
