"""show_onboarding user preference

Revision ID: i5j6k7l8m9n0
Revises: h4d5e6f7g8h9
Create Date: 2026-08-14 23:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "i5j6k7l8m9n0"
down_revision: Union[str, Sequence[str], None] = "h4d5e6f7g8h9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "show_onboarding",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "show_onboarding")
