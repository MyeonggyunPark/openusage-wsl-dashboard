from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from app.models.usage import UsageCollection, UsageSnapshot


class UsageCache:
    def __init__(self, cache_path: Path) -> None:
        self.cache_path = cache_path
        self._items: dict[str, UsageSnapshot] = {}
        self._updated_at = datetime.now(UTC)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    @property
    def updated_at(self) -> datetime:
        return self._updated_at

    def get_all(self) -> list[UsageSnapshot]:
        return list(self._items.values())

    def get_one(self, provider_id: str) -> UsageSnapshot | None:
        return self._items.get(provider_id)

    def replace_all(self, snapshots: list[UsageSnapshot]) -> None:
        self._items = {item.provider_id: item for item in snapshots}
        self._updated_at = datetime.now(UTC)
        self._persist()

    def as_collection(self, is_demo_mode: bool) -> UsageCollection:
        return UsageCollection(
            items=self.get_all(),
            updatedAt=self._updated_at,
            isDemoMode=is_demo_mode,
        )

    def _load(self) -> None:
        if not self.cache_path.exists():
            return
        payload = json.loads(self.cache_path.read_text())
        collection = UsageCollection.model_validate(payload)
        self._items = {item.provider_id: item for item in collection.items}
        self._updated_at = collection.updated_at

    def _persist(self) -> None:
        payload = {
            "items": [item.model_dump(by_alias=True, mode="json") for item in self.get_all()],
            "updatedAt": self._updated_at.isoformat(),
            "isDemoMode": False,
        }
        self.cache_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2))
