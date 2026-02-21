"""add_user_onboarding_flags

Revision ID: 004
Revises: 003
Create Date: 2026-02-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add columns as nullable
    op.add_column('user', sa.Column('onboarding_tz_confirmed', sa.Boolean(), nullable=True))
    op.add_column('user', sa.Column('onboarding_morning_confirmed', sa.Boolean(), nullable=True))
    op.add_column('user', sa.Column('onboarding_evening_confirmed', sa.Boolean(), nullable=True))

    # 2. Backfill existing users (set True)
    op.execute('UPDATE "user" SET onboarding_tz_confirmed = true, onboarding_morning_confirmed = true, onboarding_evening_confirmed = true')

    # 3. Make columns NOT NULL and add server default
    op.alter_column('user', 'onboarding_tz_confirmed', nullable=False, server_default="false")
    op.alter_column('user', 'onboarding_morning_confirmed', nullable=False, server_default="false")
    op.alter_column('user', 'onboarding_evening_confirmed', nullable=False, server_default="false")


def downgrade() -> None:
    op.drop_column('user', 'onboarding_evening_confirmed')
    op.drop_column('user', 'onboarding_morning_confirmed')
    op.drop_column('user', 'onboarding_tz_confirmed')