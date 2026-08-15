"""telegram account link on users

Revision ID: n0o1p2q3r4s5
Revises: m9n0o1p2q3r4
Create Date: 2026-08-15 16:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "n0o1p2q3r4s5"
down_revision: Union[str, Sequence[str], None] = "m9n0o1p2q3r4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("telegram_username", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("telegram_link_token", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "telegram_link_expires",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_unique_constraint(
        "uq_users_telegram_user_id", "users", ["telegram_user_id"]
    )
    op.create_unique_constraint(
        "uq_users_telegram_link_token", "users", ["telegram_link_token"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_users_telegram_link_token", "users", type_="unique")
    op.drop_constraint("uq_users_telegram_user_id", "users", type_="unique")
    op.drop_column("users", "telegram_link_expires")
    op.drop_column("users", "telegram_link_token")
    op.drop_column("users", "telegram_username")
    op.drop_column("users", "telegram_user_id")
