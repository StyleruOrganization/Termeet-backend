from fastapi import Request

from backend.src.database import async_session_maker


async def get_async_session():
    async with async_session_maker() as session:
        async with session.begin():
            yield session


async def get_rabbit(request: Request):
    return request.app.state.rabbitmq


async def get_s3_client(request: Request):
    return request.app.state.s3_client
