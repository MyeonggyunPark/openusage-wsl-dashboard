from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_usage import router as usage_router
from app.core.config import settings
from app.core.service import usage_service


@asynccontextmanager
async def lifespan(_: FastAPI):
    await usage_service.bootstrap_if_empty()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(usage_router)


@app.get("/")
async def root():
    return {
        "name": settings.app_name,
        "api": "/api/v1/usage",
        "demoMode": settings.use_demo_data,
    }
