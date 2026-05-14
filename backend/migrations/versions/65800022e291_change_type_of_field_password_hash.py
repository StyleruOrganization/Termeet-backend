"""change type of field password_hash

Revision ID: 65800022e291
Revises: c71c2068b6dd
Create Date: 2026-04-26 10:29:09.709289

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '65800022e291'
down_revision: Union[str, Sequence[str], None] = 'c71c2068b6dd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('users', 'password_hash',
                    existing_type=sa.VARCHAR(),
                    type_=sa.LargeBinary(),
                    existing_nullable=True,
                    postgresql_using='password_hash::bytea')   # 👈 явное приведение

def downgrade() -> None:
    op.alter_column('users', 'password_hash',
                    existing_type=sa.LargeBinary(),
                    type_=sa.VARCHAR(),
                    existing_nullable=True,
                    postgresql_using='password_hash::text')    # обратное преобразование