from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

from app.core.config import settings
from app.models.usage import UsageMetric, UsageSnapshot
from app.providers.base import ProviderAdapter


class CodexAdapter(ProviderAdapter):
    provider_id = "codex"
    display_name = "Codex"
    usage_url = "https://chatgpt.com/backend-api/wham/usage"

    def _candidate_paths(self) -> list[Path]:
        return [
            settings.codex_home / "auth.json",
            Path("~/.config/codex/auth.json").expanduser(),
            Path("~/.codex/auth.json").expanduser(),
        ]

    async def probe(self, use_demo_data: bool) -> UsageSnapshot:
        if use_demo_data:
            return self._demo_snapshot(
                "plus",
                [
                    UsageMetric(
                        type="progress",
                        label="5h",
                        used=34,
                        limit=100,
                        unit="percent",
                        resetsAt=self._future(hours=2),
                        periodDurationMs=18_000_000,
                        color="#1d9bf0",
                        meta={"displayMode": "remaining"},
                    ),
                    UsageMetric(
                        type="progress",
                        label="7d",
                        used=58,
                        limit=100,
                        unit="percent",
                        resetsAt=self._future(days=5),
                        periodDurationMs=604_800_000,
                        color="#3ccf91",
                        meta={"displayMode": "remaining"},
                    ),
                    UsageMetric(
                        type="progress",
                        label="Context Usage",
                        used=72_000,
                        limit=200_000,
                        unit="count",
                        color="#b7f34d",
                        meta={"displayMode": "used"},
                    ),
                ],
            )

        auth_path = next((path for path in self._candidate_paths() if path.exists()), None)
        if auth_path is None:
            return self._missing_auth_snapshot("Codex 인증 파일을 찾지 못했습니다.")

        auth = self._read_json(auth_path) or {}
        tokens = auth.get("tokens") or {}
        access_token = tokens.get("access_token")
        account_id = tokens.get("account_id")
        if not access_token:
            return self._missing_auth_snapshot("Codex access token을 찾지 못했습니다.")

        headers = {
            "accept": "application/json",
            "authorization": f"Bearer {access_token}",
            "user-agent": "openusage-dashboard/0.1",
        }
        if account_id:
            headers["chatgpt-account-id"] = str(account_id)

        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                response = await client.get(self.usage_url, headers=headers)
        except httpx.RequestError as exc:
            return self._network_error_snapshot(
                f"Codex usage API 요청에 실패했습니다: {exc.__class__.__name__}"
            )

        if response.status_code in {401, 403}:
            return self._auth_expired_snapshot("Codex 인증이 만료되었거나 거부되었습니다.")
        if response.status_code >= 400:
            return self._provider_error_snapshot(
                f"Codex usage API가 HTTP {response.status_code}를 반환했습니다."
            )

        try:
            payload = response.json()
        except ValueError:
            return self._parse_error_snapshot("Codex usage API 응답을 JSON으로 해석하지 못했습니다.")

        try:
            metrics = self._build_metrics(payload)
        except (KeyError, TypeError, ValueError) as exc:
            return self._parse_error_snapshot(f"Codex usage 응답 해석에 실패했습니다: {exc}")

        return UsageSnapshot(
            providerId=self.provider_id,
            displayName=self.display_name,
            plan=str(payload.get("plan_type") or "connected"),
            status="ok",
            sourceState="live_api",
            fetchedAt=datetime.now(UTC),
            metrics=metrics,
            warnings=[],
        )

    def _build_metrics(self, payload: dict) -> list[UsageMetric]:
        rate_limit = payload["rate_limit"]
        primary_window = rate_limit["primary_window"]
        window_metrics = [
            self._window_metric(
                self._window_label(primary_window, fallback="5h"),
                primary_window,
                color="#1d9bf0",
            ),
        ]
        secondary_window = rate_limit.get("secondary_window")
        if secondary_window is not None:
            window_metrics.append(
                self._window_metric(
                    self._window_label(secondary_window, fallback="7d"),
                    secondary_window,
                    color="#3ccf91",
                )
            )

        metrics = sorted(
            window_metrics,
            key=lambda metric: metric.period_duration_ms or float("inf"),
        )

        context_metric = self._latest_context_metric()
        if context_metric is not None:
            metrics.append(context_metric)
            return metrics

        code_review_limit = payload.get("code_review_rate_limit") or {}
        secondary_window = code_review_limit.get("secondary_window")
        if secondary_window:
            metrics.append(
                self._window_metric("Code Review", secondary_window, color="#b7f34d")
            )
        return metrics

    @staticmethod
    def _window_label(window: dict, *, fallback: str) -> str:
        duration_seconds = int(window.get("limit_window_seconds") or 0)
        if duration_seconds > 0 and duration_seconds % 86_400 == 0:
            return f"{duration_seconds // 86_400}d"
        if duration_seconds > 0 and duration_seconds % 3_600 == 0:
            return f"{duration_seconds // 3_600}h"
        return fallback

    def _window_metric(self, label: str, window: dict, *, color: str) -> UsageMetric:
        return UsageMetric(
            type="progress",
            label=label,
            used=float(window["used_percent"]),
            limit=100,
            unit="percent",
            resetsAt=datetime.fromtimestamp(window["reset_at"], UTC),
            periodDurationMs=int(window["limit_window_seconds"]) * 1000,
            color=color,
            meta={"displayMode": "remaining"},
        )

    def _latest_context_metric(self) -> UsageMetric | None:
        session_files = sorted(
            settings.codex_home.joinpath("sessions").rglob("*.jsonl"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for session_file in session_files[:5]:
            try:
                lines = session_file.read_text().splitlines()
            except OSError:
                continue
            for line in reversed(lines):
                if '"type":"token_count"' not in line:
                    continue
                try:
                    payload = json.loads(line)["payload"]
                except (json.JSONDecodeError, KeyError, TypeError):
                    continue
                info = payload.get("info") or {}
                total_usage = info.get("last_token_usage") or info.get("total_token_usage") or {}
                used = total_usage.get("total_tokens")
                limit = info.get("model_context_window")
                if used is None or limit in (None, 0):
                    continue
                return UsageMetric(
                    type="progress",
                    label="Context Usage",
                    used=float(used),
                    limit=float(limit),
                    unit="count",
                    color="#b7f34d",
                    meta={"source": "local_session", "displayMode": "used"},
                )
        return None
