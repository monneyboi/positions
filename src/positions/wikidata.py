"""Authenticated submission to the Wikibase REST API (the review "accept" path).

An edit names one allowed `operationId` from the generated operations
data (spec.py) plus its `params` and `body`; we send it verbatim — one HTTP
call, atomically or not at all. Edits address stable identities (item
ids, statement GUIDs, language codes), so drift between queueing and
accept surfaces as a loud server error rather than a silent wrong-target
edit. There is no client-side pre-flight check: the server's response
decides the outcome, uniformly for every operation:

- 200/201 → submitted; a response body `id` (a create's new QID or
  statement GUID) is recorded on the edit
- 404/409/412 → the target is gone or live state conflicts: the edit is
  stale — never force an edit through
- anything else — rejection, rate limit, server error, network failure —
  is failed: the error is shown in the TUI and the edit stays pending,
  so the human can simply accept again
"""

import os

import httpx

from . import spec

API_BASE = "https://www.wikidata.org/w/rest.php/wikibase"  # spec paths add /v1/…

STALE_CODES = (404, 409, 412)  # target gone, or live state conflicts


class SubmitError(Exception):
    """A Wikidata edit was rejected or failed; the edit stays pending."""


class SubmitConflict(Exception):
    """Live Wikidata state disagrees with the queued edit (stale)."""


def auth_client() -> httpx.Client:
    token = os.environ.get("WIKIDATA_ACCESS_TOKEN")
    if not token:
        raise SubmitError("WIKIDATA_ACCESS_TOKEN is not set (see .env.example)")
    return httpx.Client(
        timeout=60.0,
        headers={"User-Agent": spec.USER_AGENT, "Authorization": f"Bearer {token}"},
        follow_redirects=True,
    )


def _message(resp: httpx.Response) -> str:
    try:
        return str(resp.json().get("message", "")) or resp.text[:200]
    except ValueError:
        return resp.text[:200]


def submit(client: httpx.Client, edit: dict) -> str | None:
    """Submit one edit verbatim; return a new entity id if the server gave one."""
    op = spec.operations()[edit["operationId"]]
    url = API_BASE + op.path.format(**edit["params"])
    try:
        resp = client.request(op.method, url, json=edit.get("body"))
    except httpx.HTTPError as error:
        raise SubmitError(f"Wikidata edit request failed: {error}") from error
    if resp.status_code in (200, 201):
        try:
            data = resp.json()
        except ValueError:
            return None
        return data.get("id") if isinstance(data, dict) else None
    if resp.status_code in STALE_CODES:
        raise SubmitConflict(_message(resp))
    raise SubmitError(
        f"Wikidata rejected the edit ({resp.status_code}): {_message(resp)}"
    )
