"""add recovery intelligence fields

Revision ID: 6dfd61b8937e
Revises: 884ada6ffa19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "6dfd61b8937e"
down_revision: Union[str, Sequence[str], None] = "884ada6ffa19"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(
    table_name: str,
    column_name: str,
) -> bool:
    """
    Check whether a column already exists.

    This migration is intentionally defensive because the local
    development database may already contain these fields from an
    earlier schema synchronization attempt.
    """

    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = {
        column["name"]
        for column in inspector.get_columns(table_name)
    }

    return column_name in columns


def upgrade() -> None:
    """
    Add AI recovery intelligence fields to recovery_attempts.

    The checks make this migration safe for databases where the
    columns already exist but Alembic's version table was not updated.
    """

    if not _column_exists(
        "recovery_attempts",
        "recovery_probability",
    ):
        op.add_column(
            "recovery_attempts",
            sa.Column(
                "recovery_probability",
                sa.Float(),
                nullable=True,
            ),
        )

    if not _column_exists(
        "recovery_attempts",
        "decision_reason",
    ):
        op.add_column(
            "recovery_attempts",
            sa.Column(
                "decision_reason",
                sa.Text(),
                nullable=True,
            ),
        )


def downgrade() -> None:
    """
    Remove AI recovery intelligence fields.
    """

    if _column_exists(
        "recovery_attempts",
        "decision_reason",
    ):
        op.drop_column(
            "recovery_attempts",
            "decision_reason",
        )

    if _column_exists(
        "recovery_attempts",
        "recovery_probability",
    ):
        op.drop_column(
            "recovery_attempts",
            "recovery_probability",
        )