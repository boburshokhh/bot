"""Add custom_reminder table

Revision ID: 003
Revises: 002
Create Date: 2026-02-20 00:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "custom_reminder",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("time_of_day", sa.Time(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("repeat_interval_minutes", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("max_attempts_per_day", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("cycle_local_date", sa.Date(), nullable=True),
        sa.Column("attempts_sent_today", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("done_today", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("next_fire_at_utc", sa.DateTime(), nullable=True),
        sa.Column("last_sent_at_utc", sa.DateTime(), nullable=True),
        sa.Column("locked_until_utc", sa.DateTime(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_custom_reminder_user_id"), "custom_reminder", ["user_id"], unique=False)
    op.create_index(op.f("ix_custom_reminder_next_fire_at_utc"), "custom_reminder", ["next_fire_at_utc"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_custom_reminder_next_fire_at_utc"), table_name="custom_reminder")
    op.drop_index(op.f("ix_custom_reminder_user_id"), table_name="custom_reminder")
    op.drop_table("custom_reminder")
