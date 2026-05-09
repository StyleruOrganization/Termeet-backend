from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from backend.src.meetings.routers import router as meetings_router
from backend.src.auth.routers import router as auth_router
from backend.src.users.routers import router as users_router
from backend.src.lifespan import lifespan

app = FastAPI(
    title="Termeet API",
    version="1.0.0",
    description="API для Termeet",
    root_path="/api",
    lifespan=lifespan,
)

origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "https://termeet.tech",
    "https://termeet-dev.ru",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(meetings_router)
app.include_router(auth_router)
app.include_router(users_router)

Instrumentator().instrument(app).expose(app)
