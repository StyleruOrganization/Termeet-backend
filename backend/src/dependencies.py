from backend.src.database import async_session_maker


async def get_async_session():
    # Вот здесь по поподу begin()
    async with async_session_maker() as session:
        yield session
