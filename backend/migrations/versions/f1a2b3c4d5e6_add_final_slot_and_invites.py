"""add meeting final slot, set-final permission and invites

Revision ID: f1a2b3c4d5e6
Revises: e8a1b2c3d4e5
Create Date: 2026-08-14 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "e8a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "meetings",
        sa.Column("final_slot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "meetings",
        sa.Column(
            "anyone_can_set_final",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
    )
    op.add_column(
        "meetings",
        sa.Column(
            "invited_user_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("meetings", "invited_user_ids")
    op.drop_column("meetings", "anyone_can_set_final")
    op.drop_column("meetings", "final_slot")
