"""add user preferences and availability template

Revision ID: e8a1b2c3d4e5
Revises: d4e8c1a90b2f
Create Date: 2026-08-14 12:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e8a1b2c3d4e5"
down_revision: Union[str, Sequence[str], None] = "d4e8c1a90b2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "timezone",
            sa.String(length=64),
            server_default="UTC +3:00 (Москва)",
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "theme",
            sa.String(length=16),
            server_default="light",
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "suggest_prefill",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "availability_template",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "availability_template")
    op.drop_column("users", "suggest_prefill")
    op.drop_column("users", "theme")
    op.drop_column("users", "timezone")
