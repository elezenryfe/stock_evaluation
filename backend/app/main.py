from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import websocket
from app.api.v1 import analysis, stocks


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Stock Guidance Platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(stocks.router, prefix="/api/v1")
app.include_router(analysis.router, prefix="/api/v1")
app.include_router(websocket.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
