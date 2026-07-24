"""Local DuckDB world model and persistence helpers."""

import json
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

import duckdb

DEFAULT_DB = Path("positions.duckdb")

SCHEMA = """
CREATE TABLE IF NOT EXISTS position (
    qid TEXT PRIMARY KEY,
    links INTEGER NOT NULL          -- truthy P39 usage count at sync time
);

CREATE TABLE IF NOT EXISTS entity (
    qid TEXT PRIMARY KEY,
    labels JSON,
    descriptions JSON,
    aliases JSON,
    en_label TEXT,
    en_description TEXT,
    lastrevid BIGINT NOT NULL,       -- Wikidata revision of the synced entity
    is_position BOOLEAN NOT NULL DEFAULT FALSE,  -- in the P39-value universe
    synced_at TIMESTAMP NOT NULL DEFAULT now()
);

-- Synced Wikidata reality only. Proposals never enter this table.
CREATE TABLE IF NOT EXISTS claim (
    statement_id TEXT PRIMARY KEY,
    subject TEXT NOT NULL,
    property TEXT NOT NULL,
    value TEXT NOT NULL,             -- qid or +ISO time
    value_type TEXT NOT NULL,        -- 'item' | 'time'
    rank TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_claim_subject ON claim(subject);
CREATE INDEX IF NOT EXISTS idx_claim_property ON claim(property);
CREATE INDEX IF NOT EXISTS idx_claim_value ON claim(value);

-- One proposal is one atomic human decision, even when it adds two claims.
CREATE TABLE IF NOT EXISTS proposal (
    kind TEXT NOT NULL,
    position_qid TEXT NOT NULL,
    body_qid TEXT NOT NULL,
    country_qid TEXT NOT NULL,
    jurisdiction_qid TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    PRIMARY KEY (kind, position_qid)
);

CREATE TABLE IF NOT EXISTS decision (
    proposal_kind TEXT NOT NULL,
    position_qid TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('approved', 'rejected', 'skipped')),
    note TEXT,
    decided_at TIMESTAMP NOT NULL DEFAULT now(),
    submission_revision_id BIGINT,
    PRIMARY KEY (proposal_kind, position_qid)
);
"""

ClaimRows = Sequence[tuple[str, str, str, str, str]]


@contextmanager
def transaction(con: duckdb.DuckDBPyConnection) -> Iterator[None]:
    """Commit a group of writes atomically."""
    con.execute("BEGIN TRANSACTION")
    try:
        yield
    except BaseException:
        con.execute("ROLLBACK")
        raise
    else:
        con.execute("COMMIT")


def connect(db_path: Path | str = DEFAULT_DB) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(db_path))
    con.execute(SCHEMA)
    return con


def replace_claims(
    con: duckdb.DuckDBPyConnection, subject: str, claims: ClaimRows
) -> None:
    """Replace one entity's mirrored claims using the canonical row shape."""
    con.execute("DELETE FROM claim WHERE subject = ?", [subject])
    if claims:
        con.executemany(
            """
            INSERT INTO claim
                (subject, property, value, value_type, rank, statement_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (subject, prop, value, value_type, rank, statement_id)
                for prop, value, value_type, rank, statement_id in claims
            ],
        )


def upsert_entity(
    con: duckdb.DuckDBPyConnection, parsed: dict, is_position: bool
) -> None:
    """Store entity metadata and replace its mirrored Wikidata claims."""
    con.execute(
        """
        INSERT INTO entity (qid, labels, descriptions, aliases,
                            en_label, en_description, lastrevid,
                            is_position, synced_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, now())
        ON CONFLICT (qid) DO UPDATE SET
            labels = excluded.labels,
            descriptions = excluded.descriptions,
            aliases = excluded.aliases,
            en_label = excluded.en_label,
            en_description = excluded.en_description,
            lastrevid = excluded.lastrevid,
            is_position = entity.is_position OR excluded.is_position,
            synced_at = excluded.synced_at
        """,
        [
            parsed["qid"],
            json.dumps(parsed["labels"]),
            json.dumps(parsed["descriptions"]),
            json.dumps(parsed["aliases"]),
            parsed["labels"].get("en"),
            parsed["descriptions"].get("en"),
            parsed["lastrevid"],
            is_position,
        ],
    )
    replace_claims(con, parsed["qid"], parsed["claims"])


def update_entity_claims(
    con: duckdb.DuckDBPyConnection,
    qid: str,
    lastrevid: int,
    claims: ClaimRows,
) -> None:
    """Refresh claims and revision after a successful live edit."""
    con.execute(
        "UPDATE entity SET lastrevid = ?, synced_at = now() WHERE qid = ?",
        [lastrevid, qid],
    )
    replace_claims(con, qid, claims)
