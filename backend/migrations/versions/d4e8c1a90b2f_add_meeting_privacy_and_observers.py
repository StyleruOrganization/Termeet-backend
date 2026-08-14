"""add meeting privacy settings and observers

Revision ID: d4e8c1a90b2f
Revises: 227982df7bde
Create Date: 2026-08-14 11:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d4e8c1a90b2f"
down_revision: Union[str, Sequence[str], None] = "227982df7bde"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "meetings",
        sa.Column(
            "anyone_can_edit",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )
    op.add_column(
        "meetings",
        sa.Column(
            "anyone_can_delete_participants",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )
    op.add_column(
        "meetings",
        sa.Column(
            "require_login_to_vote",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "meetings",
        sa.Column(
            "observers",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.execute(
        """
        UPDATE meetings
        SET anyone_can_edit = false,
            anyone_can_delete_participants = false
        WHERE owner_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_column("meetings", "observers")
    op.drop_column("meetings", "require_login_to_vote")
    op.drop_column("meetings", "anyone_can_delete_participants")
    op.drop_column("meetings", "anyone_can_edit")
