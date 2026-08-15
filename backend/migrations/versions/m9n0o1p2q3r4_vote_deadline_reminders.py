"""vote deadline and reminder pushes

Revision ID: m9n0o1p2q3r4
Revises: l8m9n0o1p2q3
Create Date: 2026-08-15 12:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "m9n0o1p2q3r4"
down_revision: Union[str, Sequence[str], None] = "l8m9n0o1p2q3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "meetings",
        sa.Column("vote_deadline", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "meetings",
        sa.Column(
            "remind_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "meetings",
        sa.Column(
            "remind_offsets",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
    )
    op.add_column(
        "meetings",
        sa.Column(
            "remind_sent",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
    )
    op.add_column(
        "meetings",
        sa.Column(
            "lock_vote_after_deadline",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("meetings", "lock_vote_after_deadline")
    op.drop_column("meetings", "remind_sent")
    op.drop_column("meetings", "remind_offsets")
    op.drop_column("meetings", "remind_enabled")
    op.drop_column("meetings", "vote_deadline")
