from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from app.core.cache import UsageCache
from app.core.config import settings
from app.models.usage import RefreshResponse, UsageSnapshot
from app.providers.base import ProviderAdapter
from app.providers.registry import build_provider_registry


class UsageService:
    def __init__(self, cache: UsageCache, providers: list[ProviderAdapter]) -> None:
        self.cache = cache
        self.providers = providers
        self._lock: asyncio.Lock | None = None

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def collect_all(self) -> list[UsageSnapshot]:
        async with self._get_lock():
            results = await asyncio.gather(
                *(provider.probe(settings.use_demo_data) for provider in self.providers)
            )
            self.cache.replace_all(results)
            return results

    async def refresh(self) -> RefreshResponse:
        snapshots = await self.collect_all()
        return RefreshResponse(
            ok=True,
            updatedAt=self.cache.updated_at,
            providerIds=[snapshot.provider_id for snapshot in snapshots],
        )

    async def bootstrap_if_empty(self) -> None:
        if self.cache.get_all():
            return
        await self.collect_all()


cache = UsageCache(settings.cache_path)
usage_service = UsageService(cache=cache, providers=build_provider_registry())
started_at = datetime.now(UTC)
