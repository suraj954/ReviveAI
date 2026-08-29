from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RecoveryAttempt(Base):
    __tablename__ = "recovery_attempts"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    payment_id: Mapped[int] = mapped_column(
        ForeignKey("payments.id"),
        nullable=False,
        index=True,
    )

    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    attempt_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
    )

    recovered: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    provider_reference_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    def __init__(
        self,
        payment_id: int,
        action: str,
        attempt_number: int = 1,
        status: str = "pending",
        recovered: bool | None = None,
        provider_reference_id: str | None = None,
        error_message: str | None = None,
        created_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> None:
        self.payment_id = payment_id
        self.action = action
        self.attempt_number = attempt_number
        self.status = status
        self.recovered = recovered
        self.provider_reference_id = provider_reference_id
        self.error_message = error_message
        self.created_at = created_at or datetime.utcnow()
        self.completed_at = completed_at