"""On-the-fly jurisdiction-backfill candidate selection and human decisions.

Candidates are derived from the local model when needed and never stored.
The conservative eligibility rules come from research.md §3.4: the position
must be a directly typed public office with exactly one P361 statement, no
P17/P1001, and a body with exactly one non-deprecated P17 and P1001 statement.
The review path verifies the same facts against live Wikidata at every rank.

Human decisions are the only persisted review state: they live in the
decision table as tombstones so a decided position is never proposed again.
"""

import duckdb

KIND = "jurisdiction-backfill"

# Undecided positions eligible for the §3 backfill, from the local model only.
_ELIGIBLE_SQL = """
WITH public_office AS (
    SELECT DISTINCT subject AS position_qid
    FROM claim
    WHERE property = 'P31' AND value = 'Q294414'
),
single_body AS (
    SELECT subject AS position_qid, min(value) AS body_qid
    FROM claim
    WHERE property = 'P361'
    GROUP BY subject
    HAVING count(*) = 1
),
single_body_context AS (
    SELECT subject AS body_qid,
           min(value) FILTER (WHERE property = 'P17') AS country_qid,
           min(value) FILTER (WHERE property = 'P1001') AS jurisdiction_qid
    FROM claim
    WHERE property IN ('P17', 'P1001')
    GROUP BY subject
    HAVING count(*) FILTER (WHERE property = 'P17') = 1
       AND count(*) FILTER (WHERE property = 'P1001') = 1
),
eligible AS (
    SELECT p.qid AS position_qid, p.links,
           b.body_qid, context.country_qid, context.jurisdiction_qid
    FROM position p
    JOIN public_office office ON office.position_qid = p.qid
    JOIN single_body b ON b.position_qid = p.qid
    JOIN single_body_context context ON context.body_qid = b.body_qid
    WHERE NOT EXISTS (
        SELECT 1 FROM claim c
        WHERE c.subject = p.qid AND c.property IN ('P17', 'P1001')
    )
      AND NOT EXISTS (
        SELECT 1 FROM decision d
        WHERE d.proposal_kind = ? AND d.position_qid = p.qid
    )
      AND (? IS NULL OR p.qid != ?)
)
"""


def next_candidate(
    con: duckdb.DuckDBPyConnection, exclude: str | None = None
) -> tuple[str, dict] | None:
    """Return the highest-impact undecided candidate for the review UI.

    `exclude` skips one qid, so a background prefetch can select the
    candidate after the one currently on screen.
    """
    row = con.execute(
        _ELIGIBLE_SQL
        + """
        SELECT eligible.position_qid, position.en_label, eligible.links,
               eligible.body_qid, body.en_label,
               eligible.country_qid, country.en_label,
               eligible.jurisdiction_qid, jurisdiction.en_label
        FROM eligible
        JOIN entity position ON position.qid = eligible.position_qid
        LEFT JOIN entity body ON body.qid = eligible.body_qid
        LEFT JOIN entity country ON country.qid = eligible.country_qid
        LEFT JOIN entity jurisdiction
          ON jurisdiction.qid = eligible.jurisdiction_qid
        ORDER BY eligible.links DESC, eligible.position_qid
        LIMIT 1
        """,
        [KIND, exclude, exclude],
    ).fetchone()
    if row is None:
        return None
    return (
        row[0],
        {
            "label": row[1],
            "links": row[2],
            "body": {"qid": row[3], "label": row[4]},
            "country": {"qid": row[5], "label": row[6]},
            "jurisdiction": {"qid": row[7], "label": row[8]},
        },
    )


def count_candidates(con: duckdb.DuckDBPyConnection) -> int:
    """Return how many undecided candidates the local model currently has."""
    return con.execute(
        _ELIGIBLE_SQL + "SELECT count(*) FROM eligible", [KIND, None, None]
    ).fetchone()[0]


def decide(
    con: duckdb.DuckDBPyConnection,
    qid: str,
    decision: str,
    note: str | None = None,
) -> None:
    """Persist the human decision before any approved edit is submitted."""
    con.execute(
        """
        INSERT INTO decision (proposal_kind, position_qid, decision, note)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (proposal_kind, position_qid) DO UPDATE SET
            decision = excluded.decision,
            note = excluded.note,
            decided_at = now()
        """,
        [KIND, qid, decision, note],
    )


def withdraw_approval(con: duckdb.DuckDBPyConnection, qid: str) -> None:
    """Return an approval to the queue when no edit result was received."""
    con.execute(
        """
        DELETE FROM decision
        WHERE proposal_kind = ? AND position_qid = ?
          AND decision = 'approved' AND submission_revision_id IS NULL
        """,
        [KIND, qid],
    )


def record_submission(
    con: duckdb.DuckDBPyConnection, qid: str, revision_id: int
) -> None:
    con.execute(
        """
        UPDATE decision
        SET submission_revision_id = ?
        WHERE proposal_kind = ? AND position_qid = ? AND decision = 'approved'
        """,
        [revision_id, KIND, qid],
    )
