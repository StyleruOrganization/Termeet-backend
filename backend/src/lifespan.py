from typing import TYPE_CHECKING
from contextlib import asynccontextmanager

import yaml

from backend.src.broker import RabbitMQClient
from backend.src.config import config

if TYPE_CHECKING:
    from fastapi import FastAPI


@asynccontextmanager
async def lifespan_docs(app: FastAPI):
    with open("backend/docs/openapi.yaml", "w", encoding="utf-8") as f:
        yaml.dump(app.openapi(), f)
    yield


@asynccontextmanager
async def lifespan_broker(app: FastAPI):
    rabbit = RabbitMQClient(url=config.rabbitmq.rb_url)
    await rabbit.connect()
    app.state.rabbitmq = rabbit
    yield
    await rabbit.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with lifespan_docs(app), lifespan_broker(app):
        yield
