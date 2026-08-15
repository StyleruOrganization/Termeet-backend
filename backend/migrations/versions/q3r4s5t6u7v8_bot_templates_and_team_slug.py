"""bot meeting templates and team slug

Revision ID: q3r4s5t6u7v8
Revises: p2q3r4s5t6u7
Create Date: 2026-08-15 19:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "q3r4s5t6u7v8"
down_revision: Union[str, Sequence[str], None] = "p2q3r4s5t6u7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "bot_templates",
            JSONB(),
            nullable=False,
            server_default="[]",
        ),
    )
    op.add_column(
        "teams",
        sa.Column("slug", sa.String(length=16), nullable=True),
    )
    op.execute("UPDATE teams SET slug = 't' || id::text WHERE slug IS NULL")
    op.alter_column("teams", "slug", nullable=False)
    op.create_index("uq_teams_slug", "teams", ["slug"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_teams_slug", table_name="teams")
    op.drop_column("teams", "slug")
    op.drop_column("users", "bot_templates")
