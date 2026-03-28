import asyncio

from app.api.routes_usage import get_usage
from app.core.config import settings
from app.core.service import usage_service


def test_usage_endpoint_returns_collection():
    original_demo_setting = settings.use_demo_data
    settings.use_demo_data = True
    try:
        asyncio.run(usage_service.collect_all())
        collection = asyncio.run(get_usage())
    finally:
        settings.use_demo_data = original_demo_setting

    assert collection.items
    assert collection.updated_at
    assert collection.is_demo_mode is True
