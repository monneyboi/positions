"""Authenticated submission to the Wikibase REST API (the review "accept" path).

A patch is self-verifying: its `test` ops pin the live state it mutates,
and the server evaluates the whole patch atomically. So there is no
client-side pre-flight check — we send the payload verbatim and map the
response onto the queue's outcomes:

- patch:  200 → submitted; 404/409/412 → the pinned live state changed,
  the proposal is stale
- create: 201 → submitted; the response body carries the new QID

Anything else — rejection, rate limit, server error, network failure — is
a failure: the error is shown in the TUI and the proposal stays pending,
so the human can simply accept again. There is no automatic retry.
"""

import os

import httpx

API_URL = "https://www.wikidata.org/w/rest.php/wikibase/v1"
USER_AGENT = "positions/0.4 (personal Wikidata review tool; httpx)"

STALE_CODES = (404, 409, 412)  # item gone, or a test pin no longer holds


class SubmitError(Exception):
    """A Wikidata edit was rejected or failed; the proposal stays pending."""


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


def submit_patch(
    client: httpx.Client, qid: str, patch: list[dict], comment: str
) -> None:
    """Submit the patch verbatim; raise on rejection or drifted live state."""
    url = f"{API_URL}/entities/items/{qid}"
    body = {"patch": patch, "comment": comment}
    try:
        resp = client.patch(url, json=body)
    except httpx.HTTPError as error:
        raise SubmitError(f"Wikidata edit request failed: {error}") from error
    if resp.status_code == 200:
        return
    if resp.status_code in STALE_CODES:
        raise SubmitConflict(_message(resp))
    raise SubmitError(
        f"Wikidata rejected the edit ({resp.status_code}): {_message(resp)}"
    )


def submit_create(client: httpx.Client, item: dict, comment: str) -> str | None:
    """Create the item verbatim; return the new QID on success."""
    body = {"item": item, "comment": comment}
    try:
        resp = client.post(f"{API_URL}/entities/items", json=body)
    except httpx.HTTPError as error:
        raise SubmitError(f"Wikidata create request failed: {error}") from error
    if resp.status_code == 201:
        try:
            return resp.json().get("id")
        except ValueError:
            return None
    raise SubmitError(
        f"Wikidata rejected the creation ({resp.status_code}): {_message(resp)}"
    )
