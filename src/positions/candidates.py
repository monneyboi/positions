"""Jurisdiction-backfill proposal generation and persistence.

Each proposal is one atomic review action: copy both P17 and P1001 from a
position's sole P361 body. Synced claims remain in `claim`; proposals and
human decisions have their own tables.

The conservative eligibility rules come from research.md §3.4: the position
must be a directly typed public office with exactly one P361 statement, no
P17/P1001, and a body with exactly one non-deprecated P17 and P1001 statement.
The review path verifies the same facts against live Wikidata at every rank.
"""

import duckdb

from . import db as dbmod

KIND = "jurisdiction-backfill"


_CREATE_PROPOSALS_SQL = """
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
    SELECT p.qid AS position_qid,
           b.body_qid,
           context.country_qid,
           context.jurisdiction_qid
    FROM position p
    JOIN public_office office ON office.position_qid = p.qid
    JOIN single_body b ON b.position_qid = p.qid
    JOIN single_body_context context ON context.body_qid = b.body_qid
    WHERE NOT EXISTS (
        SELECT 1 FROM claim c
        WHERE c.subject = p.qid AND c.property IN ('P17', 'P1001')
    )
)
INSERT INTO proposal (kind, position_qid, body_qid, country_qid, jurisdiction_qid)
SELECT ?, position_qid, body_qid, country_qid, jurisdiction_qid
FROM eligible
ON CONFLICT DO NOTHING
"""


def create_proposals(con: duckdb.DuckDBPyConnection) -> int:
    """Refresh undecided proposals and return the pending count."""
    with dbmod.transaction(con):
        con.execute(
            """
            DELETE FROM proposal p
            WHERE p.kind = ? AND NOT EXISTS (
                SELECT 1 FROM decision d
                WHERE d.proposal_kind = p.kind
                  AND d.position_qid = p.position_qid
            )
            """,
            [KIND],
        )
        con.execute(_CREATE_PROPOSALS_SQL, [KIND])
    return count_pending(con)


def count_pending(con: duckdb.DuckDBPyConnection) -> int:
    """Return proposals that have not received a human decision."""
    return con.execute(
        """
        SELECT count(*)
        FROM proposal p
        LEFT JOIN decision d
          ON d.proposal_kind = p.kind AND d.position_qid = p.position_qid
        WHERE p.kind = ? AND d.position_qid IS NULL
        """,
        [KIND],
    ).fetchone()[0]


def next_pending(con: duckdb.DuckDBPyConnection) -> tuple[str, dict] | None:
    """Return the highest-impact undecided proposal for the review UI."""
    row = con.execute(
        """
        SELECT p.position_qid, position.en_label, coalesce(universe.links, 0),
               p.body_qid, body.en_label,
               p.country_qid, country.en_label,
               p.jurisdiction_qid, jurisdiction.en_label
        FROM proposal p
        LEFT JOIN position universe ON universe.qid = p.position_qid
        JOIN entity position ON position.qid = p.position_qid
        LEFT JOIN entity body ON body.qid = p.body_qid
        LEFT JOIN entity country ON country.qid = p.country_qid
        LEFT JOIN entity jurisdiction ON jurisdiction.qid = p.jurisdiction_qid
        LEFT JOIN decision d
          ON d.proposal_kind = p.kind AND d.position_qid = p.position_qid
        WHERE p.kind = ? AND d.position_qid IS NULL
        ORDER BY universe.links DESC, p.position_qid
        LIMIT 1
        """,
        [KIND],
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
