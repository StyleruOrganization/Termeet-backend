from typing import TYPE_CHECKING
from contextlib import asynccontextmanager

from botocore.exceptions import ClientError
from grpc import aio
import yaml
import aioboto3

from backend.src.feedback.grpc.generated.service_pb2_grpc import (
    add_FeedbackGRPCServicer_to_server,
)
from backend.src.feedback.grpc.grpc_service import FeedbackService
from backend.src.meetings.grpc.generated.meeting_create_pb2_grpc import (
    add_MeetingCreateGRPCServicer_to_server,
)
from backend.src.meetings.grpc.grpc_service import MeetingCreateService
from backend.src.broker import RabbitMQClient
from backend.src.config import config
from backend.src.database import async_session_maker

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
    add_FeedbackGRPCServicer_to_server(
        FeedbackService(async_session_maker), server
    )
    add_MeetingCreateGRPCServicer_to_server(
        MeetingCreateService(async_session_maker), server
    )
    server.add_insecure_port(f"{config.grpc.HOST}:{config.grpc.PORT}")
    await server.start()
    yield

    await server.stop(grace=5)


@asynccontextmanager
async def lifespan_s3(app: FastAPI):
    session = aioboto3.Session()

    async with session.client(
        "s3",
        aws_access_key_id=config.s3.ACCESS_KEY,
        aws_secret_access_key=config.s3.SECRET_KEY,
        endpoint_url=config.s3.ENDPOINT,
    ) as client:

        try:
            await client.create_bucket(Bucket=config.s3.BUCKET_NAME)
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code in [
                "BucketAlreadyExists",
                "BucketAlreadyOwnedByYou",
            ]:
                print(
                    f"Бакет {config.s3.BUCKET_NAME} уже существует, создание не требуется.",
                    flush=True,
                )
            else:
                raise e
        app.state.s3_client = client
        yield


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with (
        lifespan_docs(app),
        lifespan_broker(app),
        lifespan_grpc(app),
        lifespan_s3(app),
    ):
        yield
