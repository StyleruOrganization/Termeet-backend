from backend.src.database import async_session_maker


async def get_async_session():
    async with async_session_maker() as session:
        async with session.begin():
            yield session
