from sqlalchemy import inspect


def _inspector_get_table_names(conn):
    inspector = inspect(conn)
    return inspector.get_table_names()


async def test_create_tables(engine):
    need_tables = [
        "users",
        "meetings",
        "teams",
        "meetings_users"
    ]

    async with engine.connect() as conn:
        tables = await conn.run_sync(_inspector_get_table_names)

        for table in need_tables:
            assert table in tables
