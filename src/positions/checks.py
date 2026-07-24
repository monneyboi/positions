"""Audit checks: named SQL queries that produce review queues.

Each check returns rows of (qid, details-dict). The CLI refreshes the
`queue` table from these. Checks operate purely on the local model —
see research.md for the WDQS originals and the reasoning behind each.
"""

import json
from dataclasses import dataclass
from typing import Callable

import duckdb


@dataclass
class Check:
    name: str
    description: str
    run: Callable[[duckdb.DuckDBPyConnection], list[tuple[str, dict]]]


def _rows(con, sql, map_row):
    return [map_row(r) for r in con.execute(sql).fetchall()]


# research.md §3 — public offices whose P361 body already supplies the
# missing P17 and P1001. Deterministic, safest structural batch.
def jurisdiction_backfill(con):
    sql = """
    SELECT p.qid, e.en_label, p.links,
           b.value AS body, be.en_label AS body_label,
           bc.value AS country, bce.en_label AS country_label,
           bj.value AS jurisdiction, bje.en_label AS jurisdiction_label
    FROM position p
    JOIN entity e ON e.qid = p.qid
    JOIN claim t ON t.subject = p.qid AND t.property = 'P31' AND t.value = 'Q294414'
    JOIN claim b ON b.subject = p.qid AND b.property = 'P361'
    JOIN claim bc ON bc.subject = b.value AND bc.property = 'P17'
    JOIN claim bj ON bj.subject = b.value AND bj.property = 'P1001'
    LEFT JOIN entity be ON be.qid = b.value
    LEFT JOIN entity bce ON bce.qid = bc.value
    LEFT JOIN entity bje ON bje.qid = bj.value
    WHERE NOT EXISTS (SELECT 1 FROM claim c WHERE c.subject = p.qid AND c.property = 'P17')
      AND NOT EXISTS (SELECT 1 FROM claim c WHERE c.subject = p.qid AND c.property = 'P1001')
    ORDER BY p.links DESC
    """
    return _rows(
        con,
        sql,
        lambda r: (
            r[0],
            {
                "label": r[1],
                "links": r[2],
                "body": {"qid": r[3], "label": r[4]},
                "country": {"qid": r[5], "label": r[6]},
                "jurisdiction": {"qid": r[7], "label": r[8]},
            },
        ),
    )


# research.md §5 — used public offices with no direct subclass of.
def missing_p279(con):
    sql = """
    SELECT p.qid, e.en_label, p.links
    FROM position p
    JOIN entity e ON e.qid = p.qid
    JOIN claim t ON t.subject = p.qid AND t.property = 'P31' AND t.value = 'Q294414'
    WHERE NOT EXISTS (SELECT 1 FROM claim c WHERE c.subject = p.qid AND c.property = 'P279')
    ORDER BY p.links DESC
    """
    return _rows(con, sql, lambda r: (r[0], {"label": r[1], "links": r[2]}))


# research.md §6 — missing English label / description.
def missing_en_label(con):
    sql = """
    SELECT p.qid, p.links, e.labels
    FROM position p
    JOIN entity e ON e.qid = p.qid
    JOIN claim t ON t.subject = p.qid AND t.property = 'P31' AND t.value = 'Q294414'
    WHERE e.en_label IS NULL
    ORDER BY p.links DESC
    """
    return _rows(
        con,
        sql,
        lambda r: (r[0], {"links": r[1], "available_labels": json.loads(r[2] or "{}")}),
    )


def missing_en_description(con):
    sql = """
    SELECT p.qid, e.en_label, p.links
    FROM position p
    JOIN entity e ON e.qid = p.qid
    JOIN claim t ON t.subject = p.qid AND t.property = 'P31' AND t.value = 'Q294414'
    WHERE e.en_description IS NULL
    ORDER BY p.links DESC
    """
    return _rows(con, sql, lambda r: (r[0], {"label": r[1], "links": r[2]}))


# research.md §7 — Wikimedia list items used as P39 values.
def list_valued(con):
    sql = """
    SELECT p.qid, e.en_label, p.links, t.value AS list_class
    FROM position p
    JOIN entity e ON e.qid = p.qid
    JOIN claim t ON t.subject = p.qid AND t.property = 'P31'
    WHERE t.value IN ('Q13406463', 'Q19692233')
    ORDER BY p.links DESC
    """
    return _rows(
        con, sql, lambda r: (r[0], {"label": r[1], "links": r[2], "list_class": r[3]})
    )


CHECKS: dict[str, Check] = {
    c.name: c
    for c in [
        Check("jurisdiction-backfill", "P17/P1001 inheritable from P361 body (research.md §3)", jurisdiction_backfill),
        Check("missing-p279", "Public offices without subclass of (research.md §5)", missing_p279),
        Check("missing-en-label", "Public offices without English label (research.md §6)", missing_en_label),
        Check("missing-en-description", "Public offices without English description (research.md §6)", missing_en_description),
        Check("list-valued", "Wikimedia list items used as positions (research.md §7)", list_valued),
    ]
}


def refresh_queue(con: duckdb.DuckDBPyConnection, check: Check) -> int:
    rows = check.run(con)
    con.execute("DELETE FROM queue WHERE check_name = ?", [check.name])
    if rows:
        con.executemany(
            "INSERT INTO queue (check_name, qid, details) VALUES (?, ?, ?)",
            [(check.name, qid, json.dumps(details)) for qid, details in rows],
        )
    return len(rows)
