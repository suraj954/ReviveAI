"""sync recovery attempt schema

Revision ID: 884ada6ffa19
Revises: 4710dea46ec4
Create Date: 2026-08-30

Synchronizes the database schema with the current recovery models.

This migration intentionally preserves existing indexes, unique constraints,
and foreign-key cascade behavior introduced by earlier migrations.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "884ada6ffa19"
down_revision: Union[str, Sequence[str], None] = "4710dea46ec4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # =========================================================
    # RECOVERY EVENTS
    # =========================================================

    op.create_table(
        "recovery_events",
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "recovery_attempt_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "event_type",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "metadata_json",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["recovery_attempt_id"],
            ["recovery_attempts.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_recovery_events_created_at",
        "recovery_events",
        ["created_at"],
        unique=False,
    )

    op.create_index(
        "ix_recovery_events_event_type",
        "recovery_events",
        ["event_type"],
        unique=False,
    )

    op.create_index(
        "ix_recovery_events_recovery_attempt_id",
        "recovery_events",
        ["recovery_attempt_id"],
        unique=False,
    )

    # =========================================================
    # RECOVERY ATTEMPTS
    # =========================================================

    # Existing rows require a server default while adding a
    # non-nullable column.
    op.add_column(
        "recovery_attempts",
        sa.Column(
            "executed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    # Remove the temporary database default after existing rows
    # have been populated.
    op.alter_column(
        "recovery_attempts",
        "executed",
        server_default=None,
    )

    # Synchronize column lengths with the current ORM model.
    op.alter_column(
        "recovery_attempts",
        "status",
        existing_type=sa.VARCHAR(length=30),
        type_=sa.String(length=50),
        existing_nullable=False,
    )

    op.alter_column(
        "recovery_attempts",
        "provider_reference_id",
        existing_type=sa.VARCHAR(length=100),
        type_=sa.String(length=255),
        existing_nullable=True,
    )

    op.alter_column(
        "recovery_attempts",
        "recovery_payment_id",
        existing_type=sa.VARCHAR(length=100),
        type_=sa.String(length=255),
        existing_nullable=True,
    )

    # root_cause was intentionally removed from the ORM model.
    op.drop_column(
        "recovery_attempts",
        "root_cause",
    )


def downgrade() -> None:
    """Downgrade schema."""

    # =========================================================
    # RECOVERY ATTEMPTS
    # =========================================================

    op.add_column(
        "recovery_attempts",
        sa.Column(
            "root_cause",
            sa.String(length=150),
            nullable=True,
        ),
    )

    op.alter_column(
        "recovery_attempts",
        "recovery_payment_id",
        existing_type=sa.String(length=255),
        type_=sa.VARCHAR(length=100),
        existing_nullable=True,
    )

    op.alter_column(
        "recovery_attempts",
        "provider_reference_id",
        existing_type=sa.String(length=255),
        type_=sa.VARCHAR(length=100),
        existing_nullable=True,
    )

    op.alter_column(
        "recovery_attempts",
        "status",
        existing_type=sa.String(length=50),
        type_=sa.VARCHAR(length=30),
        existing_nullable=False,
    )

    op.drop_column(
        "recovery_attempts",
        "executed",
    )

    # =========================================================
    # RECOVERY EVENTS
    # =========================================================

    op.drop_index(
        "ix_recovery_events_recovery_attempt_id",
        table_name="recovery_events",
    )

    op.drop_index(
        "ix_recovery_events_event_type",
        table_name="recovery_events",
    )

    op.drop_index(
        "ix_recovery_events_created_at",
        table_name="recovery_events",
    )

    op.drop_table(
        "recovery_events",
    )