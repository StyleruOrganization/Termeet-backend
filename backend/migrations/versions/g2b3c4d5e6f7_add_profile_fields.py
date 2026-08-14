"""add user name patch fields: locale and grid window

Revision ID: g2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-08-14 14:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "g2b3c4d5e6f7"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "locale",
            sa.String(length=8),
            server_default="ru",
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "grid_window_start",
            sa.String(length=16),
            server_default="10 : 00",
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "grid_window_end",
            sa.String(length=16),
            server_default="19 : 00",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "grid_window_end")
    op.drop_column("users", "grid_window_start")
    op.drop_column("users", "locale")
