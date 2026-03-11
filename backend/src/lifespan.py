from typing import TYPE_CHECKING
from contextlib import asynccontextmanager

import yaml

if TYPE_CHECKING:
    from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI):
    with open("backend/docs/openapi_fastapi.yaml", "w", encoding="utf-8") as f:
        yaml.dump(app.openapi(), f)
    yield
