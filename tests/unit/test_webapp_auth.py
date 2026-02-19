"""Unit tests for Telegram WebApp initData validation."""
import hashlib
import hmac
from urllib.parse import urlencode

import pytest

from src.api.auth import validate_webapp_init_data


def _build_init_data(bot_token: str, values: dict[str, str]) -> str:
    parts = [f"{k}={v}" for k, v in sorted(values.items())]
    data_check_string = "\n".join(parts)
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    signature = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    payload = dict(values)
    payload["hash"] = signature
    return urlencode(payload)


def test_validate_webapp_init_data_success():
    token = "123456:test-token"
    values = {
        "auth_date": "4102444800",  # year 2100
        "query_id": "AAEAAAE",
        "user": '{"id":12345,"first_name":"Test"}',
    }
    init_data = _build_init_data(token, values)
    payload = validate_webapp_init_data(init_data, token)
    assert payload.user_id == 12345
    assert payload.query_id == "AAEAAAE"


def test_validate_webapp_init_data_invalid_hash():
    token = "123456:test-token"
    values = {
        "auth_date": "4102444800",
        "query_id": "AAEAAAE",
        "user": '{"id":12345,"first_name":"Test"}',
    }
    init_data = urlencode({**values, "hash": "bad-hash"})
    with pytest.raises(ValueError, match="Invalid initData signature"):
        validate_webapp_init_data(init_data, token)
