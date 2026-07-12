from app.providers.codex import CodexAdapter


def test_build_metrics_skips_unavailable_secondary_window(monkeypatch):
    adapter = CodexAdapter()
    monkeypatch.setattr(adapter, "_latest_context_metric", lambda: None)
    payload = {
        "rate_limit": {
            "primary_window": {
                "used_percent": 12,
                "limit_window_seconds": 18_000,
                "reset_at": 1_800_000_000,
            },
            "secondary_window": None,
        },
        "code_review_rate_limit": None,
    }

    metrics = adapter._build_metrics(payload)

    assert [metric.label for metric in metrics] == ["5h"]
    assert metrics[0].used == 12


def test_build_metrics_labels_primary_window_from_its_duration(monkeypatch):
    adapter = CodexAdapter()
    monkeypatch.setattr(adapter, "_latest_context_metric", lambda: None)
    payload = {
        "rate_limit": {
            "primary_window": {
                "used_percent": 2,
                "limit_window_seconds": 604_800,
                "reset_at": 1_800_000_000,
            },
            "secondary_window": None,
        }
    }

    metrics = adapter._build_metrics(payload)

    assert [metric.label for metric in metrics] == ["7d"]


def test_build_metrics_restores_and_prioritizes_five_hour_window(monkeypatch):
    adapter = CodexAdapter()
    monkeypatch.setattr(adapter, "_latest_context_metric", lambda: None)
    payload = {
        "rate_limit": {
            "primary_window": {
                "used_percent": 2,
                "limit_window_seconds": 604_800,
                "reset_at": 1_800_000_000,
            },
            "secondary_window": {
                "used_percent": 12,
                "limit_window_seconds": 18_000,
                "reset_at": 1_700_000_000,
            },
        }
    }

    metrics = adapter._build_metrics(payload)

    assert [metric.label for metric in metrics] == ["5h", "7d"]
    assert metrics[0].used == 12
