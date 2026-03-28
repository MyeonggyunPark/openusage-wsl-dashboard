from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


MetricType = Literal["progress", "text", "badge"]
ProviderStatus = Literal[
    "ok",
    "demo",
    "auth_missing",
    "auth_expired",
    "network_error",
    "provider_error",
    "parse_error",
]


class UsageMetric(BaseModel):
    type: MetricType
    label: str
    used: float | None = None
    limit: float | None = None
    unit: Literal["percent", "count", "currency"] | None = None
    value: str | None = None
    text: str | None = None
    color: str | None = None
    resets_at: datetime | None = Field(default=None, alias="resetsAt")
    period_duration_ms: int | None = Field(default=None, alias="periodDurationMs")
    meta: dict[str, Any] = Field(default_factory=dict)


class UsageSnapshot(BaseModel):
    provider_id: str = Field(alias="providerId")
    display_name: str = Field(alias="displayName")
    plan: str
    status: ProviderStatus
    source_state: str = Field(alias="sourceState")
    fetched_at: datetime = Field(alias="fetchedAt")
    metrics: list[UsageMetric]
    warnings: list[str] = Field(default_factory=list)


class UsageCollection(BaseModel):
    items: list[UsageSnapshot]
    updated_at: datetime = Field(alias="updatedAt")
    is_demo_mode: bool = Field(alias="isDemoMode")


class RefreshResponse(BaseModel):
    ok: bool
    updated_at: datetime = Field(alias="updatedAt")
    provider_ids: list[str] = Field(alias="providerIds")


class HealthResponse(BaseModel):
    ok: bool
    provider_count: int = Field(alias="providerCount")
    updated_at: datetime = Field(alias="updatedAt")
    is_demo_mode: bool = Field(alias="isDemoMode")
