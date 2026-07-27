"""Local proposal queue: SQLite via SQLAlchemy.

The database holds proposed edits only — never a mirror of Wikidata.
Edits arrive through `positions queue` in batches (one rationale over
one or more edits), a human decides each batch in the review TUI, and
the terminal states (submitted/rejected/stale) stay in the table as
tombstones so the same edit is never proposed again.
"""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import JSON, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

DEFAULT_DB = Path("positions.sqlite")

PENDING = "pending"
SUBMITTED = "submitted"
REJECTED = "rejected"
STALE = "stale"  # live Wikidata changed so a patch no longer applies

STATUSES = (PENDING, SUBMITTED, REJECTED, STALE)


class Base(DeclarativeBase):
    pass


class Proposal(Base):
    __tablename__ = "proposal"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch: Mapped[str] = mapped_column(index=True)  # key grouping one queued batch
    kind: Mapped[str]  # proposals.PATCH | proposals.CREATE
    entity: Mapped[str | None]  # QID; a create learns its QID on submission
    fingerprint: Mapped[str] = mapped_column(unique=True)
    payload: Mapped[list[dict] | dict] = mapped_column(JSON)  # patch | item doc
    rationale: Mapped[str]  # the batch's shared rationale
    status: Mapped[str] = mapped_column(default=PENDING, index=True)
    note: Mapped[str | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    decided_at: Mapped[datetime | None] = mapped_column(default=None)


def fingerprint(kind: str, entity: str | None, payload: object) -> str:
    """Stable identity of an edit: same kind + entity + payload → same fingerprint."""
    canonical = json.dumps(
        {"kind": kind, "entity": entity, "payload": payload}, sort_keys=True
    )
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def display_name(proposal: Proposal) -> str:
    """How lists and logs refer to a proposal: QID, or 'new item' pre-creation."""
    return proposal.entity or "new item"


def open_session(db_path: Path | str = DEFAULT_DB) -> Session:
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def enqueue(
    session: Session, batches: list[dict]
) -> tuple[list[Proposal], list[tuple[dict, str]]]:
    """Insert validated batches; skip edits whose fingerprint is known.

    Each batch gets a fresh key grouping its edits for review. Returns
    (added, skipped) where skipped entries are (edit, reason). A
    fingerprint known in ANY status is skipped: pending ones are already
    queued, the rest are tombstones of past human decisions.
    """
    added: list[Proposal] = []
    skipped: list[tuple[dict, str]] = []
    for batch in batches:
        key = uuid4().hex[:8]
        for edit in batch["edits"]:
            fp = fingerprint(edit["kind"], edit["entity"], edit["payload"])
            existing = session.scalar(select(Proposal).where(Proposal.fingerprint == fp))
            if existing is not None:
                skipped.append((edit, f"already {existing.status} as #{existing.id}"))
                continue
            proposal = Proposal(
                batch=key,
                kind=edit["kind"],
                entity=edit["entity"],
                fingerprint=fp,
                payload=edit["payload"],
                rationale=batch["rationale"],
            )
            session.add(proposal)
            added.append(proposal)
    session.commit()
    return added, skipped


def pending(session: Session) -> list[Proposal]:
    return by_status(session, PENDING)


def pending_batches(session: Session) -> list[tuple[str, list[Proposal]]]:
    """Pending proposals grouped by batch key, oldest batch first."""
    groups: dict[str, list[Proposal]] = {}
    for proposal in pending(session):
        groups.setdefault(proposal.batch, []).append(proposal)
    return list(groups.items())


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


def record_submission(
    session: Session, proposal: Proposal, created_entity: str | None = None
) -> None:
    """Mark a proposal submitted; a create learns its new QID here."""
    if created_entity is not None:
        proposal.entity = created_entity
    decide(session, proposal, SUBMITTED)
