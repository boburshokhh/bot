"""Unit tests for settings command parsing helpers."""
from src.bot.handlers.start import _extract_command_arg, _parse_hhmm


def test_extract_command_arg():
    assert _extract_command_arg("/set_interval 45") == "45"
    assert _extract_command_arg("/set_interval") == ""
    assert _extract_command_arg(None) == ""


def test_parse_hhmm_valid_and_invalid():
    assert _parse_hhmm("07:30").strftime("%H:%M") == "07:30"
    assert _parse_hhmm("24:00") is None
    assert _parse_hhmm("7:00") is None
