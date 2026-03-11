from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.src.meetings.routers import router as meetings_router
from backend.src.lifespan import lifespan

app = FastAPI(
    title="Termeet API",
    version="1.0.0",
    description="API для Termeet",
    root_path="/api",
    lifespan=lifespan
)

origins = [
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
)

app.include_router(meetings_router)
