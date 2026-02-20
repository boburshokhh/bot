"""Unit tests for morning reminder scheduling helpers."""
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.scheduler.tasks import (
    BOTS_CANT_SEND_TO_BOTS,
    _is_non_retryable_telegram_error,
    compute_next_morning_reminder_countdown,
)


def test_is_non_retryable_telegram_error_bots_forbidden():
    assert _is_non_retryable_telegram_error(Exception("Telegram server says - Forbidden: bots can't send messages to bots")) is True
    assert _is_non_retryable_telegram_error(ValueError(BOTS_CANT_SEND_TO_BOTS)) is True


def test_is_non_retryable_telegram_error_other_forbidden_with_bot():
    assert _is_non_retryable_telegram_error(Exception("Forbidden: bot was blocked by the user")) is True


def test_is_non_retryable_telegram_error_retryable():
    assert _is_non_retryable_telegram_error(Exception("Connection timeout")) is False
    assert _is_non_retryable_telegram_error(Exception("429 Too Many Requests")) is False


def test_countdown_returns_none_when_attempt_exceeds_limit():
    countdown = compute_next_morning_reminder_countdown(
        interval_minutes=60,
        max_attempts=1,
        next_attempt=2,
    )
    assert countdown is None


def test_countdown_returns_seconds_for_valid_attempt():
    countdown = compute_next_morning_reminder_countdown(
        interval_minutes=45,
        max_attempts=3,
        next_attempt=2,
    )
    assert countdown == 45 * 60


def test_countdown_sanitizes_values():
    countdown = compute_next_morning_reminder_countdown(
        interval_minutes=0,
        max_attempts=-1,
        next_attempt=1,
    )
    assert countdown is None


@pytest.mark.asyncio
async def test_send_morning_on_exception_logs_payload_with_date():
    """When _send_morning raises, log_notification is called with payload containing 'date' for dedup."""
    from src.scheduler import tasks as tasks_mod

    plan_date = date(2026, 2, 20)
    user_id = 1
    mock_user = MagicMock()
    mock_user.id = user_id
    mock_user.telegram_id = 12345

    async def mock_execute(statement):
        result = MagicMock()
        result.scalar_one_or_none.return_value = mock_user
        return result

    mock_session = AsyncMock()
    mock_session.execute = mock_execute
    mock_session.commit = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    mock_engine = MagicMock()
    mock_engine.dispose = AsyncMock()

    def mock_factory():
        return mock_session

    captured_log_payload = None

    async def capture_log(session, uid, ntype, status, payload=None):
        nonlocal captured_log_payload
        captured_log_payload = payload

    with (
        patch.object(tasks_mod, "_get_async_session") as mock_get_session,
        patch.object(tasks_mod, "log_notification", side_effect=capture_log),
        patch.object(tasks_mod, "set_awaiting_plan", AsyncMock()),
        patch("src.scheduler.tasks.Bot") as mock_bot_cls,
    ):
        mock_get_session.return_value = (mock_factory, mock_engine)
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock(side_effect=RuntimeError("send failed"))
        mock_bot.session.close = AsyncMock()
        mock_bot_cls.return_value = mock_bot

        with pytest.raises(RuntimeError, match="send failed"):
            await tasks_mod._send_morning(user_id, plan_date, 0)

    assert captured_log_payload is not None
    assert "date" in captured_log_payload
    assert captured_log_payload["date"] == plan_date.isoformat()
