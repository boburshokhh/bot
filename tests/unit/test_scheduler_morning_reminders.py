"""Unit tests for morning reminder scheduling helpers."""
from src.scheduler.tasks import compute_next_morning_reminder_countdown


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
