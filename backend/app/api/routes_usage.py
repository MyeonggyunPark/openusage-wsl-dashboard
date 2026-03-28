from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.core.service import cache, usage_service
from app.models.usage import HealthResponse, UsageCollection, UsageSnapshot

router = APIRouter(prefix="/api/v1", tags=["usage"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        ok=True,
        providerCount=len(cache.get_all()),
        updatedAt=cache.updated_at,
        isDemoMode=settings.use_demo_data,
    )


@router.get("/usage", response_model=UsageCollection)
async def get_usage() -> UsageCollection:
    return cache.as_collection(is_demo_mode=settings.use_demo_data)


@router.get("/usage/{provider_id}", response_model=UsageSnapshot)
async def get_provider_usage(provider_id: str) -> UsageSnapshot:
    snapshot = cache.get_one(provider_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="provider_not_found")
    return snapshot


@router.post("/refresh")
async def refresh_all():
    return await usage_service.refresh()
