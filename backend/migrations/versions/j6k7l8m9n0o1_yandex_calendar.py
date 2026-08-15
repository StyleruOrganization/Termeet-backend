"""oauth profile fields and meeting calendar event map

Revision ID: j6k7l8m9n0o1
Revises: i5j6k7l8m9n0
Create Date: 2026-08-15 10:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "j6k7l8m9n0o1"
down_revision: Union[str, Sequence[str], None] = "i5j6k7l8m9n0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "oauth_accounts",
        sa.Column("yandex_login", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "oauth_accounts",
        sa.Column("yandex_email", sa.String(length=256), nullable=True),
    )
    op.add_column(
        "oauth_accounts",
        sa.Column("display_name", sa.String(length=256), nullable=True),
    )
    op.add_column(
        "meetings",
        sa.Column(
            "calendar_events",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("meetings", "calendar_events")
    op.drop_column("oauth_accounts", "display_name")
    op.drop_column("oauth_accounts", "yandex_email")
    op.drop_column("oauth_accounts", "yandex_login")
