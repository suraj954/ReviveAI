from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(UTC)


class RecoveryEvent(Base):
    """
    Immutable audit event for a recovery attempt lifecycle.

    RecoveryAttempt represents the current state.

    RecoveryEvent represents historical facts about transitions
    and decisions that occurred during the lifecycle.

    Events should be append-only. Existing audit events should
    never be modified or deleted during normal application flow.
    """

    __tablename__ = "recovery_events"

    # ============================================================
    # PRIMARY KEY
    # ============================================================

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # ============================================================
    # RECOVERY ATTEMPT RELATIONSHIP
    # ============================================================

    recovery_attempt_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "recovery_attempts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    recovery_attempt: Mapped["RecoveryAttempt"] = relationship(
        "RecoveryAttempt",
        back_populates="events",
    )

    # ============================================================
    # EVENT INFORMATION
    # ============================================================

    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Optional structured context stored as JSON text.
    metadata_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # ============================================================
    # TIMESTAMP
    # ============================================================

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        index=True,
    )

    # ============================================================
    # PYTHON-SIDE DEFAULTS
    # ============================================================

    def __init__(self, **kwargs):
        """
        Apply timestamp defaults immediately so objects are usable
        before database persistence.
        """

        kwargs.setdefault(
            "metadata_json",
            None,
        )
        kwargs.setdefault(
            "created_at",
            utc_now(),
        )

        super().__init__(**kwargs)