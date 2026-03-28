from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.models.usage import UsageMetric, UsageSnapshot


class ProviderAdapter(ABC):
    provider_id: str
    display_name: str

    @abstractmethod
    async def probe(self, use_demo_data: bool) -> UsageSnapshot:
        raise NotImplementedError

    def _missing_auth_snapshot(self, message: str) -> UsageSnapshot:
        return UsageSnapshot(
            providerId=self.provider_id,
            displayName=self.display_name,
            plan="unknown",
            status="auth_missing",
            sourceState="credentials_missing",
            fetchedAt=datetime.now(UTC),
            metrics=[],
            warnings=[message],
        )

    def _auth_expired_snapshot(self, message: str) -> UsageSnapshot:
        return UsageSnapshot(
            providerId=self.provider_id,
            displayName=self.display_name,
            plan="unknown",
            status="auth_expired",
            sourceState="credentials_expired",
            fetchedAt=datetime.now(UTC),
            metrics=[],
            warnings=[message],
        )

    def _network_error_snapshot(self, message: str) -> UsageSnapshot:
        return UsageSnapshot(
            providerId=self.provider_id,
            displayName=self.display_name,
            plan="unknown",
            status="network_error",
            sourceState="network_error",
            fetchedAt=datetime.now(UTC),
            metrics=[],
            warnings=[message],
        )

    def _provider_error_snapshot(self, message: str, plan: str = "unknown") -> UsageSnapshot:
        return UsageSnapshot(
            providerId=self.provider_id,
            displayName=self.display_name,
            plan=plan,
            status="provider_error",
            sourceState="provider_error",
            fetchedAt=datetime.now(UTC),
            metrics=[],
            warnings=[message],
        )

    def _parse_error_snapshot(self, message: str, plan: str = "unknown") -> UsageSnapshot:
        return UsageSnapshot(
            providerId=self.provider_id,
            displayName=self.display_name,
            plan=plan,
            status="parse_error",
            sourceState="parse_error",
            fetchedAt=datetime.now(UTC),
            metrics=[],
            warnings=[message],
        )

    def _demo_snapshot(self, plan: str, metrics: list[UsageMetric]) -> UsageSnapshot:
        return UsageSnapshot(
            providerId=self.provider_id,
            displayName=self.display_name,
            plan=plan,
            status="demo",
            sourceState="demo_seed",
            fetchedAt=datetime.now(UTC),
            metrics=metrics,
            warnings=["실제 인증 정보 연결 전까지 데모 데이터가 표시됩니다."],
        )

    @staticmethod
    def _read_json(path: Path) -> dict | None:
        if not path.exists():
            return None
        import json

        return json.loads(path.read_text())

    @staticmethod
    def _future(hours: int = 0, days: int = 0) -> datetime:
        return datetime.now(UTC) + timedelta(hours=hours, days=days)
