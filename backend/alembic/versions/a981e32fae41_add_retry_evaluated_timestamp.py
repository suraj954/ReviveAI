"""add retry evaluated timestamp

Revision ID: a981e32fae41
Revises: 6dfd61b8937e
Create Date: 2026-09-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a981e32fae41"
down_revision: Union[str, Sequence[str], None] = "6dfd61b8937e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add retry evaluation timestamp and index."""

    op.add_column(
        "recovery_attempts",
        sa.Column(
            "retry_evaluated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_recovery_attempts_retry_evaluated_at",
        "recovery_attempts",
        ["retry_evaluated_at"],
        unique=False,
    )


def downgrade() -> None:
    """Remove retry evaluation timestamp and index."""

    op.drop_index(
        "ix_recovery_attempts_retry_evaluated_at",
        table_name="recovery_attempts",
    )

    op.drop_column(
        "recovery_attempts",
        "retry_evaluated_at",
    )