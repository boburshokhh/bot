"""Pytest fixtures: db, redis, mock telegram."""
import os
import pytest

# Set test env before importing app
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:test-token")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/planning_bot_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("WEBHOOK_SECRET", "test-secret")


@pytest.fixture
def sample_plan_text():
    return """1. Прочитать отчёт
2. Встреча в 11:00
3. Тренировка"""


@pytest.fixture
def sample_plan_multiline():
    return """
    First task
    2. Second task
    3) Third
    """
