"""Make existing timestamps timezone aware

Revision ID: 4710dea46ec4
Revises: d5b8ba3b6edc
Create Date: 2026-08-30

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "4710dea46ec4"
down_revision: Union[str, Sequence[str], None] = "d5b8ba3b6edc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Convert existing timestamps to timezone-aware UTC timestamps."""

    op.alter_column(
        "payments",
        "created_at",
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )

    op.alter_column(
        "recovery_attempts",
        "created_at",
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )

    op.alter_column(
        "recovery_attempts",
        "completed_at",
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True,
        postgresql_using="completed_at AT TIME ZONE 'UTC'",
    )

    op.alter_column(
        "webhook_events",
        "received_at",
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        postgresql_using="received_at AT TIME ZONE 'UTC'",
    )


def downgrade() -> None:
    """Convert timestamps back to timezone-naive UTC values."""

    op.alter_column(
        "webhook_events",
        "received_at",
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=False,
        postgresql_using="received_at AT TIME ZONE 'UTC'",
    )

    op.alter_column(
        "recovery_attempts",
        "completed_at",
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=True,
        postgresql_using="completed_at AT TIME ZONE 'UTC'",
    )

    op.alter_column(
        "recovery_attempts",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=False,
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )

    op.alter_column(
        "payments",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=False,
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )