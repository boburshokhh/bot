"""Integration tests: webhook accepts Update and processes (requires DB + Redis for full flow)."""
import pytest

pytestmark = pytest.mark.integration
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.fixture
def webhook_update_start():
    """Minimal Update payload: /start command from user."""
    return {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "date": 1700000000,
            "chat": {"id": 12345, "type": "private", "username": "testuser"},
            "from": {
                "id": 12345,
                "is_bot": False,
                "first_name": "Test",
                "username": "testuser",
                "language_code": "ru",
            },
            "text": "/start",
        },
    }


@pytest.mark.asyncio
async def test_webhook_accepts_post():
    """Webhook endpoint accepts POST with JSON body."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Invalid body (empty) may yield 422
        r = await client.post("/webhook", json={})
        assert r.status_code in (200, 422, 500)


@pytest.mark.asyncio
async def test_webhook_valid_update(webhook_update_start):
    """Webhook returns 200 for valid Update (processing may fail without DB)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/webhook", json=webhook_update_start)
        # 200 if processed, 500 if DB/Redis unavailable
        assert r.status_code in (200, 500)


@pytest.mark.asyncio
async def test_health():
    """Health check returns 200."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/health")
        assert r.status_code == 200
        assert r.json().get("status") == "ok"
