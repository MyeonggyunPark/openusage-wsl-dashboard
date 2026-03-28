from __future__ import annotations

from app.providers.base import ProviderAdapter
from app.providers.claude import ClaudeAdapter
from app.providers.codex import CodexAdapter
from app.providers.copilot import CopilotAdapter


def build_provider_registry() -> list[ProviderAdapter]:
    return [
        CodexAdapter(),
        ClaudeAdapter(),
        CopilotAdapter(),
    ]
