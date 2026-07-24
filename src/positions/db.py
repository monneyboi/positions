"""Local DuckDB world model."""

import json
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
    is_position BOOLEAN NOT NULL DEFAULT FALSE,  -- in the P39-value universe
    synced_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS claim (
    subject TEXT NOT NULL,
    property TEXT NOT NULL,
    value TEXT NOT NULL,            -- qid or +ISO time
    value_type TEXT NOT NULL,       -- 'item' | 'time'
    rank TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_claim_subject ON claim(subject);
CREATE INDEX IF NOT EXISTS idx_claim_property ON claim(property);
CREATE INDEX IF NOT EXISTS idx_claim_value ON claim(value);

-- Review queues produced by checks.
CREATE TABLE IF NOT EXISTS queue (
    check_name TEXT NOT NULL,
    qid TEXT NOT NULL,
    details JSON,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    PRIMARY KEY (check_name, qid)
);

-- Human decisions on queue items. Nothing is submitted without one.
CREATE TABLE IF NOT EXISTS decision (
    check_name TEXT NOT NULL,
    qid TEXT NOT NULL,
    decision TEXT NOT NULL,         -- 'approved' | 'rejected' | 'skipped'
    note TEXT,
    decided_at TIMESTAMP NOT NULL DEFAULT now(),
    PRIMARY KEY (check_name, qid)
);
"""


def connect(db_path: Path | str = DEFAULT_DB) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(db_path))
    con.execute(SCHEMA)
    return con


def upsert_entity(con: duckdb.DuckDBPyConnection, parsed: dict, is_position: bool):
    claims = parsed.pop("claims")
    con.execute(
        """
        INSERT INTO entity (qid, labels, descriptions, aliases,
                            en_label, en_description, is_position, synced_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, now())
        ON CONFLICT (qid) DO UPDATE SET
            labels = excluded.labels,
            descriptions = excluded.descriptions,
            aliases = excluded.aliases,
            en_label = excluded.en_label,
            en_description = excluded.en_description,
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
            is_position,
        ],
    )
    con.execute("DELETE FROM claim WHERE subject = ?", [parsed["qid"]])
    if claims:
        con.executemany(
            "INSERT INTO claim (subject, property, value, value_type, rank) VALUES (?, ?, ?, ?, ?)",
            [(parsed["qid"], prop, val, vtype, rank) for prop, val, vtype, rank in claims],
        )
