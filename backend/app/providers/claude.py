from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from app.core.config import settings
from app.models.usage import UsageMetric, UsageSnapshot
from app.providers.base import ProviderAdapter


class ClaudeAdapter(ProviderAdapter):
    provider_id = "claude"
    display_name = "Claude"
    usage_url = "https://api.anthropic.com/api/oauth/usage"
    refresh_url = "https://platform.claude.com/v1/oauth/token"
    refresh_client_id = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
    refresh_scope = "user:profile user:inference user:sessions:claude_code user:mcp_servers"
    oauth_beta = "oauth-2025-04-20"
    statusline_cache_path = Path("~/.claude/dashboard-rate-limits.json").expanduser()

    async def probe(self, use_demo_data: bool) -> UsageSnapshot:
        if use_demo_data:
            return self._demo_snapshot(
                "pro",
                [
                    UsageMetric(
                        type="progress",
                        label="5h",
                        used=22,
                        limit=100,
                        unit="percent",
                        resetsAt=self._future(hours=3),
                        periodDurationMs=18_000_000,
                        color="#8a7dff",
                        meta={"displayMode": "remaining"},
                    ),
                    UsageMetric(
                        type="progress",
                        label="7d",
                        used=41,
                        limit=100,
                        unit="percent",
                        resetsAt=self._future(days=4),
                        periodDurationMs=604_800_000,
                        color="#1d9bf0",
                        meta={"displayMode": "remaining"},
                    ),
                    UsageMetric(
                        type="progress",
                        label="Context Usage",
                        used=94_000,
                        limit=200_000,
                        unit="count",
                        color="#ffb347",
                        meta={"displayMode": "used"},
                    ),
                ],
            )

        credentials_path = settings.claude_credentials_path
        if not credentials_path.exists():
            return self._missing_auth_snapshot("Claude credentials 파일을 찾지 못했습니다.")

        auth = self._read_json(credentials_path) or {}
        oauth = auth.get("claudeAiOauth") or {}
        access_token = oauth.get("accessToken")
        refresh_token = oauth.get("refreshToken")
        plan = str(oauth.get("subscriptionType") or "connected")
        if not access_token:
            return self._missing_auth_snapshot("Claude access token을 찾지 못했습니다.")

        statusline_snapshot = self._statusline_cache_snapshot(plan=plan)
        if statusline_snapshot is not None:
            return statusline_snapshot

        expires_at_ms = oauth.get("expiresAt")
        if self._is_expired(expires_at_ms) and refresh_token:
            oauth = await self._refresh_oauth(credentials_path, auth, oauth)
            access_token = oauth.get("accessToken")
            refresh_token = oauth.get("refreshToken")
        elif self._is_expired(expires_at_ms):
            return self._auth_expired_snapshot("Claude access token이 만료되었고 refresh token이 없습니다.")

        snapshot = await self._fetch_usage(access_token=str(access_token), plan=plan)
        if snapshot.status in {"auth_expired", "auth_missing"} and refresh_token:
            refreshed = await self._refresh_oauth(credentials_path, auth, oauth)
            new_access_token = refreshed.get("accessToken")
            if not new_access_token:
                return self._auth_expired_snapshot("Claude 토큰 갱신에 실패했습니다.")
            return await self._fetch_usage(access_token=str(new_access_token), plan=plan)
        if snapshot.status == "provider_error" and any("HTTP 429" in warning for warning in snapshot.warnings):
            statusline_snapshot = self._statusline_cache_snapshot(plan=plan)
            if statusline_snapshot is not None:
                return statusline_snapshot
            fallback = self._local_usage_fallback(plan=plan)
            if fallback is not None:
                return fallback
        return snapshot

    async def _fetch_usage(self, *, access_token: str, plan: str) -> UsageSnapshot:
        headers = {
            "accept": "application/json",
            "authorization": f"Bearer {access_token}",
            "content-type": "application/json",
            "anthropic-beta": self.oauth_beta,
            "user-agent": "openusage-dashboard/0.1",
        }
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                response = await client.get(self.usage_url, headers=headers)
        except httpx.RequestError as exc:
            return self._network_error_snapshot(
                f"Claude usage API 요청에 실패했습니다: {exc.__class__.__name__}"
            )

        if response.status_code in {401, 403}:
            return self._auth_expired_snapshot("Claude 인증이 만료되었거나 거부되었습니다.")
        if response.status_code >= 400:
            return self._provider_error_snapshot(
                f"Claude usage API가 HTTP {response.status_code}를 반환했습니다.",
                plan=plan,
            )

        try:
            payload = response.json()
        except ValueError:
            return self._parse_error_snapshot(
                "Claude usage API 응답을 JSON으로 해석하지 못했습니다.",
                plan=plan,
            )

        try:
            metrics = [
                self._usage_metric("5h", payload["five_hour"], color="#8a7dff"),
                self._usage_metric("7d", payload["seven_day"], color="#1d9bf0"),
            ]
            extra_usage = payload.get("extra_usage") or {}
            if extra_usage.get("is_enabled"):
                monthly_limit = float(extra_usage.get("monthly_limit") or 0)
                used_credits = float(extra_usage.get("used_credits") or 0)
                if monthly_limit > 0:
                    metrics.append(
                        UsageMetric(
                            type="progress",
                            label="Extra Usage",
                            used=used_credits,
                            limit=monthly_limit,
                            unit="currency",
                            color="#ffb347",
                        )
                    )
                else:
                    metrics.append(
                        UsageMetric(
                            type="text",
                            label="Extra Usage",
                            value=f"{used_credits / 100:.2f} {extra_usage.get('currency') or 'USD'}",
                        )
                    )
        except (KeyError, TypeError, ValueError) as exc:
            return self._parse_error_snapshot(
                f"Claude usage 응답 해석에 실패했습니다: {exc}",
                plan=plan,
            )

        return UsageSnapshot(
            providerId=self.provider_id,
            displayName=self.display_name,
            plan=plan,
            status="ok",
            sourceState="live_api",
            fetchedAt=datetime.now(UTC),
            metrics=metrics,
            warnings=[],
        )

    def _usage_metric(self, label: str, window: dict, *, color: str) -> UsageMetric:
        resets_at = window.get("resets_at")
        return UsageMetric(
            type="progress",
            label=label,
            used=float(window["utilization"]),
            limit=100,
            unit="percent",
            resetsAt=datetime.fromisoformat(str(resets_at).replace("Z", "+00:00"))
            if resets_at
            else None,
            periodDurationMs=18_000_000 if label == "5h" else 604_800_000,
            color=color,
            meta={"displayMode": "remaining"},
        )

    def _statusline_cache_snapshot(self, *, plan: str) -> UsageSnapshot | None:
        path = self.statusline_cache_path
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return None

        rate_limits = payload.get("rate_limits") or {}
        five_hour = rate_limits.get("five_hour")
        seven_day = rate_limits.get("seven_day")
        context_window = payload.get("context_window") or {}
        context_size = context_window.get("context_window_size")
        current_usage = context_window.get("current_usage") or {}
        if not five_hour and not seven_day:
            return None
        if not context_size:
            return None

        current_tokens = int(current_usage.get("input_tokens") or 0)
        current_tokens += int(current_usage.get("output_tokens") or 0)
        current_tokens += int(current_usage.get("cache_creation_input_tokens") or 0)
        current_tokens += int(current_usage.get("cache_read_input_tokens") or 0)
        if current_tokens <= 0:
            used_percentage = context_window.get("used_percentage")
            if used_percentage is not None:
                current_tokens = int(float(used_percentage) * float(context_size) / 100)

        metrics: list[UsageMetric] = []
        if five_hour:
            metrics.append(self._statusline_rate_metric("5h", five_hour, color="#8a7dff"))
        if seven_day:
            metrics.append(self._statusline_rate_metric("7d", seven_day, color="#1d9bf0"))
        metrics.append(
            UsageMetric(
                type="progress",
                label="Context Usage",
                used=float(current_tokens),
                limit=float(context_size),
                unit="count",
                color="#ffb347",
                meta={"displayMode": "used", "source": "statusline_cache"},
            )
        )

        return UsageSnapshot(
            providerId=self.provider_id,
            displayName=self.display_name,
            plan=plan,
            status="ok",
            sourceState="statusline_cache",
            fetchedAt=datetime.fromtimestamp(path.stat().st_mtime, UTC),
            metrics=metrics,
            warnings=[],
        )

    def _statusline_rate_metric(self, label: str, window: dict, *, color: str) -> UsageMetric:
        resets_at = window.get("resets_at")
        return UsageMetric(
            type="progress",
            label=label,
            used=float(window["used_percentage"]),
            limit=100,
            unit="percent",
            resetsAt=datetime.fromtimestamp(float(resets_at), UTC) if resets_at else None,
            periodDurationMs=18_000_000 if label == "5h" else 604_800_000,
            color=color,
            meta={"displayMode": "remaining", "source": "statusline_cache"},
        )

    def _local_usage_fallback(self, *, plan: str) -> UsageSnapshot | None:
        projects_root = Path("~/.claude/projects").expanduser()
        if not projects_root.exists():
            return None

        now = datetime.now(UTC)
        window_5h = now - timedelta(hours=5)
        window_7d = now - timedelta(days=7)
        total_5h = 0
        total_7d = 0
        latest_timestamp: datetime | None = None
        latest_total_tokens = 0
        latest_model: str | None = None

        for path in projects_root.rglob("*.jsonl"):
            try:
                lines = path.read_text().splitlines()
            except OSError:
                continue
            for line in lines:
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if payload.get("type") != "assistant":
                    continue
                message = payload.get("message") or {}
                model = message.get("model")
                usage = message.get("usage") or {}
                if not usage or not model or str(model).startswith("<synthetic>"):
                    continue
                timestamp_raw = payload.get("timestamp")
                if not timestamp_raw:
                    continue
                try:
                    timestamp = datetime.fromisoformat(str(timestamp_raw).replace("Z", "+00:00"))
                except ValueError:
                    continue

                total_tokens = int(usage.get("input_tokens") or 0)
                total_tokens += int(usage.get("output_tokens") or 0)
                total_tokens += int(usage.get("cache_creation_input_tokens") or 0)
                total_tokens += int(usage.get("cache_read_input_tokens") or 0)

                if timestamp >= window_5h:
                    total_5h += total_tokens
                if timestamp >= window_7d:
                    total_7d += total_tokens
                if latest_timestamp is None or timestamp >= latest_timestamp:
                    latest_timestamp = timestamp
                    latest_total_tokens = total_tokens
                    latest_model = str(model)

        if latest_timestamp is None:
            return None

        context_limit = self._context_window_for(plan=plan, model=latest_model)
        metrics = [
            UsageMetric(
                type="text",
                label="5h",
                value=self._format_token_count(total_5h),
                color="#8a7dff",
                meta={"source": "local_session"},
            ),
            UsageMetric(
                type="text",
                label="7d",
                value=self._format_token_count(total_7d),
                color="#1d9bf0",
                meta={"source": "local_session"},
            ),
            UsageMetric(
                type="progress",
                label="Context Usage",
                used=float(latest_total_tokens),
                limit=float(context_limit),
                unit="count",
                color="#ffb347",
                meta={"displayMode": "used", "source": "local_session"},
            ),
        ]

        return UsageSnapshot(
            providerId=self.provider_id,
            displayName=self.display_name,
            plan=plan,
            status="ok",
            sourceState="local_session",
            fetchedAt=now,
            metrics=metrics,
            warnings=["Claude usage API가 HTTP 429를 반환해 로컬 세션 로그 기준으로 표시합니다."],
        )

    async def _refresh_oauth(
        self,
        credentials_path: Path,
        auth_payload: dict,
        oauth: dict,
    ) -> dict:
        refresh_token = oauth.get("refreshToken")
        if not refresh_token:
            return oauth

        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.refresh_client_id,
            "scope": self.refresh_scope,
        }
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "user-agent": "openusage-dashboard/0.1",
        }
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                response = await client.post(self.refresh_url, json=payload, headers=headers)
        except httpx.RequestError:
            return oauth

        if response.status_code >= 400:
            return oauth

        try:
            refreshed = response.json()
        except ValueError:
            return oauth

        access_token = refreshed.get("access_token")
        next_refresh_token = refreshed.get("refresh_token")
        expires_in = refreshed.get("expires_in")
        if not access_token or not next_refresh_token or not expires_in:
            return oauth

        updated_oauth = {
            **oauth,
            "accessToken": access_token,
            "refreshToken": next_refresh_token,
            "expiresAt": int(
                (datetime.now(UTC) + timedelta(seconds=int(expires_in))).timestamp() * 1000
            ),
        }
        auth_payload["claudeAiOauth"] = updated_oauth
        try:
            credentials_path.write_text(json.dumps(auth_payload, ensure_ascii=True, indent=2))
        except OSError:
            pass
        return updated_oauth

    def _is_expired(self, expires_at_ms: int | float | None) -> bool:
        if not expires_at_ms:
            return False
        expires_at = datetime.fromtimestamp(float(expires_at_ms) / 1000, UTC)
        return expires_at <= datetime.now(UTC) + timedelta(minutes=5)

    def _context_window_for(self, *, plan: str, model: str | None) -> int:
        lowered_model = (model or "").lower()
        if plan.lower() == "enterprise":
            return 500_000
        if "haiku-4-5" in lowered_model:
            return 200_000
        return 200_000

    def _format_token_count(self, value: int) -> str:
        if value >= 1_000_000:
            return f"{value / 1_000_000:.1f}M tok"
        if value >= 1_000:
            return f"{value / 1_000:.1f}k tok"
        return f"{value} tok"
