"""add recovery intelligence and scheduling fields

Revision ID: d5b8ba3b6edc
Revises: b22c561065f7
Create Date: 2026-08-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d5b8ba3b6edc"
down_revision: Union[str, Sequence[str], None] = "b22c561065f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # =========================================================
    # PAYMENTS
    # =========================================================

    op.add_column(
        "payments",
        sa.Column(
            "failure_code",
            sa.String(length=100),
            nullable=True,
        ),
    )

    op.add_column(
        "payments",
        sa.Column(
            "failure_reason",
            sa.String(length=255),
            nullable=True,
        ),
    )

    op.add_column(
        "payments",
        sa.Column(
            "failure_description",
            sa.Text(),
            nullable=True,
        ),
    )

    # Existing rows need a value during migration.
    op.add_column(
        "payments",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    op.alter_column(
        "payments",
        "updated_at",
        server_default=None,
    )

    op.create_index(
        "ix_payments_status",
        "payments",
        ["status"],
        unique=False,
    )

    # =========================================================
    # RECOVERY ATTEMPTS - AI AUDIT + SCHEDULING
    # =========================================================

    op.add_column(
        "recovery_attempts",
        sa.Column(
            "recovery_probability",
            sa.Float(),
            nullable=True,
        ),
    )

    op.add_column(
        "recovery_attempts",
        sa.Column(
            "decision_reason",
            sa.Text(),
            nullable=True,
        ),
    )

    op.add_column(
        "recovery_attempts",
        sa.Column(
            "root_cause",
            sa.String(length=150),
            nullable=True,
        ),
    )

    op.add_column(
        "recovery_attempts",
        sa.Column(
            "guardrail_reason",
            sa.Text(),
            nullable=True,
        ),
    )

    op.add_column(
        "recovery_attempts",
        sa.Column(
            "scheduled_for",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.add_column(
        "recovery_attempts",
        sa.Column(
            "executed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.add_column(
        "recovery_attempts",
        sa.Column(
            "recovery_payment_id",
            sa.String(length=100),
            nullable=True,
        ),
    )

    op.add_column(
        "recovery_attempts",
        sa.Column(
            "recovered_amount",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "recovery_attempts",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    op.alter_column(
        "recovery_attempts",
        "updated_at",
        server_default=None,
    )

    # Recovery order IDs and recovery payment IDs must be unique.
    op.drop_index(
        "ix_recovery_attempts_provider_reference_id",
        table_name="recovery_attempts",
    )

    op.create_index(
        "ix_recovery_attempts_provider_reference_id",
        "recovery_attempts",
        ["provider_reference_id"],
        unique=True,
    )

    op.create_index(
        "ix_recovery_attempts_recovery_payment_id",
        "recovery_attempts",
        ["recovery_payment_id"],
        unique=True,
    )

    op.create_index(
        "ix_recovery_attempts_scheduled_for",
        "recovery_attempts",
        ["scheduled_for"],
        unique=False,
    )

    op.create_index(
        "ix_recovery_attempts_status",
        "recovery_attempts",
        ["status"],
        unique=False,
    )

    op.create_unique_constraint(
        "uq_recovery_attempt_payment_number",
        "recovery_attempts",
        ["payment_id", "attempt_number"],
    )

    # Ensure deleting a payment also removes its recovery attempts.
    op.drop_constraint(
        "recovery_attempts_payment_id_fkey",
        "recovery_attempts",
        type_="foreignkey",
    )

    op.create_foreign_key(
        "fk_recovery_attempts_payment_id",
        "recovery_attempts",
        "payments",
        ["payment_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # =========================================================
    # WEBHOOK EVENTS - PROCESSING AUDIT
    # =========================================================

    op.add_column(
        "webhook_events",
        sa.Column(
            "error_message",
            sa.Text(),
            nullable=True,
        ),
    )

    op.add_column(
        "webhook_events",
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_webhook_events_event_type",
        "webhook_events",
        ["event_type"],
        unique=False,
    )

    op.create_index(
        "ix_webhook_events_status",
        "webhook_events",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""

    # =========================================================
    # WEBHOOK EVENTS
    # =========================================================

    op.drop_index(
        "ix_webhook_events_status",
        table_name="webhook_events",
    )

    op.drop_index(
        "ix_webhook_events_event_type",
        table_name="webhook_events",
    )

    op.drop_column(
        "webhook_events",
        "processed_at",
    )

    op.drop_column(
        "webhook_events",
        "error_message",
    )

    # =========================================================
    # RECOVERY ATTEMPTS
    # =========================================================

    op.drop_constraint(
        "fk_recovery_attempts_payment_id",
        "recovery_attempts",
        type_="foreignkey",
    )

    op.create_foreign_key(
        "recovery_attempts_payment_id_fkey",
        "recovery_attempts",
        "payments",
        ["payment_id"],
        ["id"],
    )

    op.drop_constraint(
        "uq_recovery_attempt_payment_number",
        "recovery_attempts",
        type_="unique",
    )

    op.drop_index(
        "ix_recovery_attempts_status",
        table_name="recovery_attempts",
    )

    op.drop_index(
        "ix_recovery_attempts_scheduled_for",
        table_name="recovery_attempts",
    )

    op.drop_index(
        "ix_recovery_attempts_recovery_payment_id",
        table_name="recovery_attempts",
    )

    op.drop_index(
        "ix_recovery_attempts_provider_reference_id",
        table_name="recovery_attempts",
    )

    op.create_index(
        "ix_recovery_attempts_provider_reference_id",
        "recovery_attempts",
        ["provider_reference_id"],
        unique=False,
    )

    op.drop_column(
        "recovery_attempts",
        "updated_at",
    )

    op.drop_column(
        "recovery_attempts",
        "recovered_amount",
    )

    op.drop_column(
        "recovery_attempts",
        "recovery_payment_id",
    )

    op.drop_column(
        "recovery_attempts",
        "executed_at",
    )

    op.drop_column(
        "recovery_attempts",
        "scheduled_for",
    )

    op.drop_column(
        "recovery_attempts",
        "guardrail_reason",
    )

    op.drop_column(
        "recovery_attempts",
        "root_cause",
    )

    op.drop_column(
        "recovery_attempts",
        "decision_reason",
    )

    op.drop_column(
        "recovery_attempts",
        "recovery_probability",
    )

    # =========================================================
    # PAYMENTS
    # =========================================================

    op.drop_index(
        "ix_payments_status",
        table_name="payments",
    )

    op.drop_column(
        "payments",
        "updated_at",
    )

    op.drop_column(
        "payments",
        "failure_description",
    )

    op.drop_column(
        "payments",
        "failure_reason",
    )

    op.drop_column(
        "payments",
        "failure_code",
    )