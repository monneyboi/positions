"""Local proposal queue: SQLite via SQLAlchemy.

The database holds proposed edits only — never a mirror of Wikidata.
Proposals arrive through `positions queue`, a human decides each one in the
review TUI, and the terminal states (submitted/rejected/stale) stay in the
table as tombstones so the same edit is never proposed again.
"""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import JSON, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

DEFAULT_DB = Path("positions.sqlite")

PENDING = "pending"
SUBMITTED = "submitted"
REJECTED = "rejected"
STALE = "stale"  # live Wikidata changed so the proposal no longer applies

STATUSES = (PENDING, SUBMITTED, REJECTED, STALE)


class Base(DeclarativeBase):
    pass


class Proposal(Base):
    __tablename__ = "proposal"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity: Mapped[str]
    fingerprint: Mapped[str] = mapped_column(unique=True)
    statements: Mapped[list[dict]] = mapped_column(JSON)
    summary: Mapped[str]
    rationale: Mapped[str] = mapped_column(default="")
    sources: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(default=PENDING, index=True)
    note: Mapped[str | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    decided_at: Mapped[datetime | None] = mapped_column(default=None)
    submission_revision_id: Mapped[int | None] = mapped_column(default=None)


def fingerprint(entity: str, statements: list[dict]) -> str:
    """Stable identity of an edit: same entity + statements, same fingerprint."""
    canonical = json.dumps(
        {
            "entity": entity,
            "statements": sorted(statements, key=lambda s: (s["property"], s["value"])),
        },
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def open_session(db_path: Path | str = DEFAULT_DB) -> Session:
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def enqueue(
    session: Session, payloads: list[dict]
) -> tuple[list[Proposal], list[tuple[dict, str]]]:
    """Insert validated payloads; skip payloads whose fingerprint is known.

    Returns (added, skipped) where skipped entries are (payload, reason).
    A fingerprint known in ANY status is skipped: pending ones are already
    queued, the rest are tombstones of past human decisions.
    """
    added: list[Proposal] = []
    skipped: list[tuple[dict, str]] = []
    for payload in payloads:
        fp = fingerprint(payload["entity"], payload["statements"])
        existing = session.scalar(select(Proposal).where(Proposal.fingerprint == fp))
        if existing is not None:
            skipped.append((payload, f"already {existing.status} as #{existing.id}"))
            continue
        proposal = Proposal(
            entity=payload["entity"],
            fingerprint=fp,
            statements=payload["statements"],
            summary=payload["summary"],
            rationale=payload.get("rationale", ""),
            sources=payload.get("sources", []),
        )
        session.add(proposal)
        added.append(proposal)
    session.commit()
    return added, skipped


def pending(session: Session) -> list[Proposal]:
    return by_status(session, PENDING)


def by_status(session: Session, status: str | None) -> list[Proposal]:
    """All proposals, oldest first, optionally filtered to one status."""
    query = select(Proposal).order_by(Proposal.id)
    if status is not None:
        query = query.where(Proposal.status == status)
    return list(session.scalars(query))


def decide(
    session: Session, proposal: Proposal, status: str, note: str | None = None
) -> None:
    """Record a terminal human decision (or staleness) on a proposal."""
    proposal.status = status
    proposal.note = note
    proposal.decided_at = datetime.now(UTC)
    session.commit()


def record_submission(session: Session, proposal: Proposal, revision_id: int) -> None:
    proposal.submission_revision_id = revision_id
    decide(session, proposal, SUBMITTED)
