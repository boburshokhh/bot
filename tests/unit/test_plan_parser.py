"""Unit tests for plan parser."""
import pytest

from src.logic.plan_parser import parse_plan_lines, validate_plan_text, MAX_PLAN_LENGTH, MAX_TASKS


def test_parse_empty():
    assert parse_plan_lines("") == []
    assert parse_plan_lines("   \n\n  ") == []


def test_parse_simple_lines():
    text = "Task one\nTask two\nTask three"
    assert parse_plan_lines(text) == ["Task one", "Task two", "Task three"]


def test_parse_strips_numbering():
    text = "1. First\n2. Second\n3) Third"
    assert parse_plan_lines(text) == ["First", "Second", "Third"]


def test_parse_drops_empty_lines():
    text = "A\n\nB\n\n\nC"
    assert parse_plan_lines(text) == ["A", "B", "C"]


def test_parse_crlf():
    text = "Line1\r\nLine2\r\nLine3"
    assert parse_plan_lines(text) == ["Line1", "Line2", "Line3"]


def test_parse_whitespace_stripped():
    text = "  Task one  \n   Task two   "
    assert parse_plan_lines(text) == ["Task one", "Task two"]


def test_validate_empty():
    ok, msg = validate_plan_text("")
    assert ok is False
    assert "пуст" in msg


def test_validate_whitespace_only():
    ok, msg = validate_plan_text("   \n  ")
    assert ok is False


def test_validate_too_long():
    ok, msg = validate_plan_text("x" * (MAX_PLAN_LENGTH + 1))
    assert ok is False
    assert "длин" in msg or str(MAX_PLAN_LENGTH) in msg


def test_validate_ok(sample_plan_text):
    ok, msg = validate_plan_text(sample_plan_text)
    assert ok is True
    assert msg == ""


def test_validate_no_tasks():
    # Only numbering, no text -> no tasks
    ok, msg = validate_plan_text("1.\n2.\n3.")
    assert ok is False
    assert "задач" in msg or "пункт" in msg


def test_parse_max_tasks():
    lines = [f"{i}. Task {i}" for i in range(MAX_TASKS + 10)]
    text = "\n".join(lines)
    result = parse_plan_lines(text)
    assert len(result) == MAX_TASKS
