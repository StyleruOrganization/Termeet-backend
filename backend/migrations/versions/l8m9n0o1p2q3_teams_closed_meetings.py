"""teams members, photos, closed meetings, contacts

Revision ID: l8m9n0o1p2q3
Revises: k7l8m9n0o1p2
Create Date: 2026-08-15 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "l8m9n0o1p2q3"
down_revision: Union[str, Sequence[str], None] = "k7l8m9n0o1p2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("avatar_key", sa.String(length=256), nullable=True)
    )
    op.add_column(
        "users",
        sa.Column("contact_email", sa.String(length=256), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("contact_telegram", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "users", sa.Column("contact_vk", sa.String(length=256), nullable=True)
    )
    op.add_column(
        "teams", sa.Column("photo_key", sa.String(length=256), nullable=True)
    )
    op.alter_column(
        "teams",
        "description",
        existing_type=sa.String(),
        type_=sa.String(length=400),
        existing_nullable=False,
        server_default="",
    )
    op.create_table(
        "teams_users",
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("team_id", "user_id"),
    )
    op.add_column(
        "meetings",
        sa.Column(
            "is_closed",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "meetings",
        sa.Column(
            "invite_only_vote",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("meetings", "invite_only_vote")
    op.drop_column("meetings", "is_closed")
    op.drop_table("teams_users")
    op.drop_column("teams", "photo_key")
    op.drop_column("users", "contact_vk")
    op.drop_column("users", "contact_telegram")
    op.drop_column("users", "contact_email")
    op.drop_column("users", "avatar_key")
