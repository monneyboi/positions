"""WDQS client with pagination and retry."""

import time
from collections.abc import Callable, Iterable
from itertools import batched

import httpx

WDQS_URL = "https://query.wikidata.org/sparql"
USER_AGENT = "positions/0.1 (personal Wikidata audit tool; httpx)"
REVISION_CHUNK_SIZE = 1000

# The full P39-value universe with usage counts. ORDER BY makes OFFSET
# pagination stable. Each page re-runs the aggregation (~15 s) but that's
# fine for a sync job.
POSITION_UNIVERSE_QUERY = """
SELECT ?position (COUNT(*) AS ?links) WHERE {
  ?person wdt:P39 ?position .
} GROUP BY ?position
ORDER BY ?position
LIMIT __LIMIT__ OFFSET __OFFSET__
"""

# WDQS can contain stale duplicate schema:version triples. Fetch all of
# them and pick the maximum client-side; server-side MAX + GROUP BY can
# trigger a Blazegraph StackOverflowError with a large VALUES clause.
REVISION_LOOKUP_QUERY = """
SELECT ?entity ?revision WHERE {
  VALUES ?entity { __VALUES__ }
  ?entity schema:version ?revision .
}
"""


class WdqsError(Exception):
    pass


def query(
    sparql: str,
    retries: int = 5,
    on_retry: Callable[[str], None] | None = None,
    use_post: bool = False,
) -> list[dict]:
    """Run a SPARQL query, return bindings as plain dicts of values."""
    last_error: Exception | None = None
    with httpx.Client(
        timeout=180.0,
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    ) as client:
        for attempt in range(retries):
            try:
                headers = {"Accept": "application/sparql-results+json"}
                if use_post:
                    resp = client.post(
                        WDQS_URL,
                        data={"query": sparql, "format": "json"},
                        headers=headers,
                    )
                else:
                    resp = client.get(
                        WDQS_URL,
                        params={"query": sparql, "format": "json"},
                        headers=headers,
                    )
                if resp.status_code in (429, 500, 502, 503, 504):
                    raise WdqsError(f"WDQS HTTP {resp.status_code}")
                resp.raise_for_status()
                data = resp.json()
                return [
                    {k: v["value"] for k, v in binding.items()}
                    for binding in data["results"]["bindings"]
                ]
            # httpx.HTTPError covers transport failures (incl. truncated
            # responses); ValueError covers malformed JSON from the gateway.
            except (WdqsError, httpx.HTTPError, ValueError) as e:
                last_error = e
                wait = min(2**attempt * 5, 120)
                if on_retry is not None:
                    on_retry(
                        f"request {attempt + 1}/{retries} failed ({e}); "
                        f"retrying in {wait}s"
                    )
                time.sleep(wait)
    raise WdqsError(f"WDQS failed after {retries} attempts: {last_error}")


def position_universe(
    page_size: int = 5000,
    max_items: int | None = None,
    on_status: Callable[[str], None] | None = None,
):
    """Yield (qid, links) for every item used as a value of P39."""
    offset = 0
    page = 1
    while True:
        limit = page_size
        if max_items is not None:
            remaining = max_items - offset
            if remaining <= 0:
                return
            limit = min(limit, remaining)
        if on_status is not None:
            on_status(
                f"page {page}: requesting up to {limit:,} rows from offset {offset:,}"
            )
        rows = query(
            POSITION_UNIVERSE_QUERY.replace("__LIMIT__", str(limit)).replace(
                "__OFFSET__", str(offset)
            ),
            on_retry=on_status,
        )
        if not rows:
            if on_status is not None:
                on_status(f"page {page}: no rows returned")
            return
        for row in rows:
            qid = row["position"].rsplit("/", 1)[-1]
            yield qid, int(row["links"])
        offset += len(rows)
        if on_status is not None:
            on_status(f"page {page}: received {len(rows):,} rows ({offset:,} total)")
        if len(rows) < limit:
            return
        page += 1


def remote_revisions(
    qids: Iterable[str],
    chunk_size: int = REVISION_CHUNK_SIZE,
    on_retry: Callable[[str], None] | None = None,
    on_chunk: Callable[[int, int], None] | None = None,
) -> dict[str, int]:
    """Return the maximum WDQS schema:version for each QID."""
    unique_qids = list(dict.fromkeys(qids))
    if not unique_qids:
        return {}

    total_chunks = (len(unique_qids) + chunk_size - 1) // chunk_size
    revisions: dict[str, int] = {}
    for page, batch in enumerate(batched(unique_qids, chunk_size), start=1):
        values = " ".join(f"wd:{qid}" for qid in batch)
        rows = query(
            REVISION_LOOKUP_QUERY.replace("__VALUES__", values),
            on_retry=on_retry,
            use_post=True,
        )
        for row in rows:
            qid = row["entity"].rsplit("/", 1)[-1]
            revision = int(row["revision"])
            if revision > revisions.get(qid, -1):
                revisions[qid] = revision
        if on_chunk is not None:
            on_chunk(page, total_chunks)
    return revisions
