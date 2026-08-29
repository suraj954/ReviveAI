from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class RecoveryAttempt(Base):
    """
    Immutable-ish audit record for one bounded recovery intervention.

    A recovery attempt is NOT considered successful merely because
    a new Razorpay order was created.

    recovered=True only after a verified successful payment event
    for the recovery order.
    """

    __tablename__ = "recovery_attempts"

    __table_args__ = (
        UniqueConstraint(
            "payment_id",
            "attempt_number",
            name="uq_recovery_attempt_payment_number",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    payment_id: Mapped[int] = mapped_column(
        ForeignKey(
            "payments.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    attempt_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
        index=True,
    )

    # AI decision audit.
    recovery_probability: Mapped[float | None] = mapped_column(
        nullable=True,
    )

    decision_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    root_cause: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    guardrail_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Razorpay recovery order.
    provider_reference_id: Mapped[str | None] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=True,
    )

    recovery_payment_id: Mapped[str | None] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=True,
    )

    recovered: Mapped[bool | None] = mapped_column(
        Boolean,
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

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    payment: Mapped["Payment"] = relationship(
        back_populates="recovery_attempts",
    )