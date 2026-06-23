from typing import TYPE_CHECKING
from contextlib import asynccontextmanager

from grpc import aio
import yaml

from backend.grpc.generated.service_pb2_grpc import (
    add_FeedbackServicer_to_server,
)
from backend.grpc.grpc_service import FeedbackService
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
async def lifespan_grpc(app: FastAPI):
    server = aio.server()
    add_FeedbackServicer_to_server(FeedbackService(), server)
    server.add_insecure_port("[::]:50051")
    await server.start()
    yield

    await server.stop(grace=5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with lifespan_docs(app), lifespan_broker(app), lifespan_grpc(app):
        yield
