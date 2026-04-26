"""add default value to slots in meetings

Revision ID: f5f799165d35
Revises: 65800022e291
Create Date: 2026-04-26 17:30:12.910218

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f5f799165d35'
down_revision: Union[str, Sequence[str], None] = '65800022e291'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Устанавливаем значение по умолчанию для существующей колонки
    op.alter_column(
        'meetings',
        'slots',
        server_default='[]',   # строка, которая будет подставлена БД
        existing_type=sa.JSON(),  # укажите тип, если нужно (JSON или JSONB)
        existing_nullable=True
    )


def downgrade() -> None:
    # Убираем значение по умолчанию
    op.alter_column(
        'meetings',
        'slots',
        server_default=None,
        existing_type=sa.JSON(),
        existing_nullable=True
    )
