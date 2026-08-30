from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(UTC)


class RecoveryAttempt(Base):
    """
    Durable record of a payment recovery decision and its lifecycle.

    Important:
    Creating a RecoveryAttempt does NOT mean revenue was recovered.

    Recovery is considered successful only after a verified provider
    payment success event marks the attempt as completed/recovered.
    """

    __tablename__ = "recovery_attempts"

    # ============================================================
    # PRIMARY KEY
    # ============================================================

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # ============================================================
    # PAYMENT RELATIONSHIP
    # ============================================================

    payment_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("payments.id"),
        nullable=False,
        index=True,
    )

    payment: Mapped["Payment"] = relationship(
        "Payment",
        back_populates="recovery_attempts",
    )

    # ============================================================
    # DECISION INFORMATION
    # ============================================================

    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    attempt_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    recovery_probability: Mapped[float | None] = mapped_column(
        nullable=True,
    )

    decision_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # ============================================================
    # GUARDRAIL INFORMATION
    # ============================================================

    guardrail_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # ============================================================
    # LIFECYCLE STATE
    # ============================================================

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
    )

    executed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # None  -> outcome unknown / awaiting payment
    # True  -> verified recovery succeeded
    # False -> recovery failed / blocked / cancelled
    recovered: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        default=None,
    )

    # ============================================================
    # EXECUTION / PROVIDER REFERENCES
    # ============================================================

    provider_reference_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    recovery_payment_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    recovered_amount: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # ============================================================
    # TIMESTAMPS
    # ============================================================

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    executed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    scheduled_for: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    # ============================================================
    # PYTHON-SIDE DEFAULTS
    # ============================================================

    def __init__(self, **kwargs):
        """
        Apply defaults immediately.

        SQLAlchemy column defaults are normally applied during INSERT,
        but tests and service-layer logic may inspect objects before
        database persistence.
        """

        kwargs.setdefault("attempt_number", 1)
        kwargs.setdefault("status", "pending")
        kwargs.setdefault("executed", False)
        kwargs.setdefault("recovered", None)

        kwargs.setdefault("recovery_probability", None)
        kwargs.setdefault("decision_reason", None)
        kwargs.setdefault("guardrail_reason", None)

        kwargs.setdefault("provider_reference_id", None)
        kwargs.setdefault("recovery_payment_id", None)
        kwargs.setdefault("recovered_amount", None)
        kwargs.setdefault("error_message", None)

        kwargs.setdefault("executed_at", None)
        kwargs.setdefault("scheduled_for", None)
        kwargs.setdefault("completed_at", None)

        kwargs.setdefault("created_at", utc_now())
        kwargs.setdefault("updated_at", utc_now())

        super().__init__(**kwargs)