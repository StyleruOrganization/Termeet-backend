"""refactor slots in meetings

Revision ID: b4b87ef7b5ce
Revises: 2546af58a223
Create Date: 2026-05-02 10:11:46.993255

"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa  # noqa

# revision identifiers, used by Alembic.
revision: str = "b4b87ef7b5ce"
down_revision: Union[str, Sequence[str], None] = "2546af58a223"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Преобразование существующих данных: старый формат -> новый
    op.execute(
        """
    DO $$
    DECLARE
        rec RECORD;
        new_slots JSONB;
        elem JSONB;
        name_key TEXT;
        user_id_val TEXT;
        slots_val JSONB;
    BEGIN
        FOR rec IN SELECT id, slots FROM meetings WHERE slots IS NOT NULL LOOP
            new_slots := '[]'::JSONB;
            IF jsonb_typeof(rec.slots) != 'array' THEN
                CONTINUE;
            END IF;
            FOR elem IN SELECT * FROM jsonb_array_elements(rec.slots) LOOP
                -- Извлекаем ключ имени (все ключи, кроме 'user_id')
                SELECT key INTO name_key
                FROM jsonb_object_keys(elem) AS key
                WHERE key != 'user_id'
                LIMIT 1;
                IF name_key IS NULL THEN
                    CONTINUE;
                END IF;
                slots_val := elem -> name_key;
                user_id_val := elem ->> 'user_id';
                new_slots := new_slots || jsonb_build_object(
                    'user_id', user_id_val,
                    'name', name_key,
                    'slots', slots_val
                );
            END LOOP;
            UPDATE meetings SET slots = new_slots WHERE id = rec.id;
        END LOOP;
    END $$;
    """
    )


def downgrade() -> None:
    # Обратное преобразование: новый формат -> старый
    op.execute(
        """
    DO $$
    DECLARE
        rec RECORD;
        new_slots JSONB;
        elem JSONB;
        name_key TEXT;
        user_id_val TEXT;
        slots_val JSONB;
    BEGIN
        FOR rec IN SELECT id, slots FROM meetings WHERE slots IS NOT NULL LOOP
            new_slots := '[]'::JSONB;
            IF jsonb_typeof(rec.slots) != 'array' THEN
                CONTINUE;
            END IF;
            FOR elem IN SELECT * FROM jsonb_array_elements(rec.slots) LOOP
                name_key := elem ->> 'name';
                slots_val := elem -> 'slots';
                user_id_val := elem ->> 'user_id';
                IF user_id_val IS NULL THEN
                    new_slots := new_slots || jsonb_build_object(name_key, slots_val);
                ELSE
                    new_slots := new_slots || jsonb_build_object(
                        name_key, slots_val,
                        'user_id', user_id_val
                    );
                END IF;
            END LOOP;
            UPDATE meetings SET slots = new_slots WHERE id = rec.id;
        END LOOP;
    END $$;
    """
    )
