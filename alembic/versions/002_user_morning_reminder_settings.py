"""Add per-user morning reminder settings.

Revision ID: 002
Revises: 001
Create Date: 2026-02-19 00:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("morning_reminder_interval_minutes", sa.Integer(), nullable=False, server_default="60"),
    )
    op.add_column(
        "user",
        sa.Column("morning_reminder_max_attempts", sa.Integer(), nullable=False, server_default="1"),
    )
    op.alter_column("user", "morning_reminder_interval_minutes", server_default=None)
    op.alter_column("user", "morning_reminder_max_attempts", server_default=None)


def downgrade() -> None:
    op.drop_column("user", "morning_reminder_max_attempts")
    op.drop_column("user", "morning_reminder_interval_minutes")
