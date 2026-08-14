"""oauth tokens, notification prefs

Revision ID: h4d5e6f7g8h9
Revises: g2b3c4d5e6f7
Create Date: 2026-08-14 22:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h4d5e6f7g8h9"
down_revision: Union[str, Sequence[str], None] = "g2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "notify_on_vote",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "notify_on_final",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
    )
    op.add_column(
        "oauth_accounts",
        sa.Column("access_token", sa.Text(), nullable=True),
    )
    op.add_column(
        "oauth_accounts",
        sa.Column("refresh_token", sa.Text(), nullable=True),
    )
    op.add_column(
        "oauth_accounts",
        sa.Column("scopes", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "oauth_accounts",
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("oauth_accounts", "token_expires_at")
    op.drop_column("oauth_accounts", "scopes")
    op.drop_column("oauth_accounts", "refresh_token")
    op.drop_column("oauth_accounts", "access_token")
    op.drop_column("users", "notify_on_final")
    op.drop_column("users", "notify_on_vote")
