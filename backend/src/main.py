from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Конструктор рамок Лего",
    version="1.0.0",
    description="API для конструктора рамок Лего",
    root_path="/api"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Здесь измени на url от Николая
)

# Здесь потом добавляй роуты
