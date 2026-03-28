from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import httpx

from app.models.usage import UsageMetric, UsageSnapshot
from app.providers.base import ProviderAdapter


class CopilotAdapter(ProviderAdapter):
    provider_id = "copilot"
    display_name = "Copilot"
    usage_url = "https://api.github.com/copilot_internal/user"
    config_path = Path("~/.copilot/config.json").expanduser()

    async def probe(self, use_demo_data: bool) -> UsageSnapshot:
        if use_demo_data:
            return self._demo_snapshot(
                "pro",
                [
                    UsageMetric(
                        type="text",
                        label="Inline Suggestions",
                        value="Included",
                        color="#3ccf91",
                    ),
                    UsageMetric(
                        type="text",
                        label="Chat messages",
                        value="Included",
                        color="#ff8c42",
                    ),
                    UsageMetric(
                        type="progress",
                        label="Premium requests",
                        used=1.9,
                        limit=100,
                        unit="percent",
                        resetsAt=self._future(days=18),
                        periodDurationMs=2_592_000_000,
                        color="#1d9bf0",
                        meta={"displayMode": "used"},
                    ),
                ],
            )

        gh_path = shutil.which("gh")
        token = self._resolve_token(gh_path)
        if not token:
            return self._missing_auth_snapshot(
                "Copilot 조회용 GitHub 토큰을 찾지 못했습니다. gh auth login 또는 GITHUB_TOKEN을 설정하세요."
            )

        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                response = await client.get(
                    self.usage_url,
                    headers={
                        "accept": "application/json",
                        "authorization": f"token {token}",
                        "editor-version": "vscode/1.96.2",
                        "editor-plugin-version": "copilot-chat/0.26.7",
                        "user-agent": "GitHubCopilotChat/0.26.7",
                        "x-github-api-version": "2025-04-01",
                    },
                )
        except httpx.RequestError as exc:
            return self._network_error_snapshot(
                f"Copilot usage API 요청에 실패했습니다: {exc.__class__.__name__}"
            )

        if response.status_code in {401, 403}:
            return self._auth_expired_snapshot("Copilot 인증이 만료되었거나 거부되었습니다.")
        if response.status_code >= 400:
            return self._provider_error_snapshot(
                f"Copilot usage API가 HTTP {response.status_code}를 반환했습니다."
            )

        try:
            payload = response.json()
        except ValueError:
            return self._parse_error_snapshot("Copilot usage API 응답을 JSON으로 해석하지 못했습니다.")

        try:
            metrics = self._build_metrics(payload)
        except (KeyError, TypeError, ValueError) as exc:
            return self._parse_error_snapshot(f"Copilot usage 응답 해석에 실패했습니다: {exc}")

        return UsageSnapshot(
            providerId=self.provider_id,
            displayName=self.display_name,
            plan=self._normalize_plan(
                payload.get("access_type_sku") or payload.get("copilot_plan") or "connected"
            ),
            status="ok",
            sourceState="live_api",
            fetchedAt=datetime.now(UTC),
            metrics=metrics,
            warnings=[],
        )

    def _resolve_token(self, gh_path: str | None) -> str | None:
        for env_name in ("OPENUSAGE_COPILOT_TOKEN", "COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
            value = os.environ.get(env_name)
            if value:
                return value
        if self.config_path.exists():
            try:
                config = json.loads(self.config_path.read_text())
            except (OSError, ValueError, TypeError):
                config = {}
            tokens = config.get("copilot_tokens") or {}
            token = next((value for value in tokens.values() if isinstance(value, str) and value), None)
            if token:
                return token
        if gh_path is None:
            return None
        try:
            result = subprocess.run(
                [gh_path, "auth", "token"],
                check=False,
                capture_output=True,
                text=True,
                timeout=3,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        token = result.stdout.strip()
        return token if result.returncode == 0 and token else None

    def _build_metrics(self, payload: dict) -> list[UsageMetric]:
        quota_snapshots = payload.get("quota_snapshots") or {}
        reset_at = payload.get("quota_reset_date") or payload.get("limited_user_reset_date")
        metrics: list[UsageMetric] = []

        completions = quota_snapshots.get("completions")
        if completions:
            metrics.append(self._copilot_metric("Inline Suggestions", completions, reset_at, color="#3ccf91"))

        chat = quota_snapshots.get("chat")
        if chat:
            metrics.append(self._copilot_metric("Chat messages", chat, reset_at, color="#ff8c42"))

        premium = quota_snapshots.get("premium_interactions")
        if premium:
            metrics.append(
                self._copilot_metric("Premium requests", premium, reset_at, color="#1d9bf0")
            )

        if not metrics and payload.get("monthly_quotas"):
            monthly = payload["monthly_quotas"]
            limited = payload.get("limited_user_quotas") or {}
            if "chat" in monthly:
                metrics.append(
                    UsageMetric(
                        type="progress",
                        label="Chat messages",
                        used=float(monthly["chat"] - limited.get("chat", 0)),
                        limit=float(monthly["chat"]),
                        unit="percent",
                        resetsAt=self._parse_reset_date(reset_at),
                        periodDurationMs=2_592_000_000,
                        color="#ff8c42",
                    )
                )
            if "completions" in monthly:
                metrics.append(
                    UsageMetric(
                        type="progress",
                        label="Inline Suggestions",
                        used=float(monthly["completions"] - limited.get("completions", 0)),
                        limit=float(monthly["completions"]),
                        unit="percent",
                        resetsAt=self._parse_reset_date(reset_at),
                        periodDurationMs=2_592_000_000,
                        color="#3ccf91",
                    )
                )

        return metrics

    def _copilot_metric(
        self,
        label: str,
        snapshot: dict,
        reset_at: str | None,
        *,
        color: str,
    ) -> UsageMetric:
        if snapshot.get("unlimited"):
            return UsageMetric(
                type="text",
                label=label,
                value="Included",
                color=color,
            )
        entitlement = float(snapshot["entitlement"])
        remaining = float(snapshot["remaining"])
        return UsageMetric(
            type="progress",
            label=label,
            used=entitlement - remaining,
            limit=entitlement,
            unit="percent",
            resetsAt=self._parse_reset_date(reset_at),
            periodDurationMs=2_592_000_000,
            color=color,
            meta={"displayMode": "used"},
        )

    def _parse_reset_date(self, value: str | None) -> datetime | None:
        if not value:
            return None
        if "T" in value:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return datetime.fromisoformat(f"{value}T00:00:00+00:00")

    def _normalize_plan(self, plan: object) -> str:
        value = str(plan).strip()
        lowered = value.lower()
        if "individual" in lowered:
            return "pro"
        if "monthly_subscriber" in lowered:
            return "pro"
        if "business" in lowered:
            return "business"
        if "enterprise" in lowered:
            return "enterprise"
        return lowered or "connected"
