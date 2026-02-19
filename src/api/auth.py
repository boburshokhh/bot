"""Telegram WebApp auth helpers and dependencies."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
from urllib.parse import parse_qsl

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Settings
from src.db.models import User
from src.db.session import get_async_session
from src.services.user import get_or_create_user, get_user_by_telegram_id


@dataclass
class WebAppAuthPayload:
    user_id: int
    auth_date: int
    query_id: str | None
    raw: dict[str, str]


def validate_webapp_init_data(init_data: str, bot_token: str, max_age_seconds: int = 24 * 3600) -> WebAppAuthPayload:
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.get("hash")
    if not received_hash:
        raise ValueError("Missing hash in initData")

    data_check_parts = [f"{k}={v}" for k, v in sorted(pairs.items()) if k != "hash"]
    data_check_string = "\n".join(data_check_parts)

    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    calc_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc_hash, received_hash):
        raise ValueError("Invalid initData signature")

    auth_date_raw = pairs.get("auth_date")
    if not auth_date_raw or not auth_date_raw.isdigit():
        raise ValueError("Invalid auth_date")
    auth_date = int(auth_date_raw)
    now_ts = int(datetime.now(timezone.utc).timestamp())
    if now_ts - auth_date > max_age_seconds:
        raise ValueError("initData expired")

    user_raw = pairs.get("user")
    if not user_raw:
        raise ValueError("Missing user in initData")
    try:
        user = json.loads(user_raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid user JSON in initData") from exc
    tg_user_id = user.get("id")
    if not isinstance(tg_user_id, int):
        raise ValueError("Invalid user id in initData")

    return WebAppAuthPayload(
        user_id=tg_user_id,
        auth_date=auth_date,
        query_id=pairs.get("query_id"),
        raw=pairs,
    )


async def get_webapp_user(
    x_telegram_init_data: str = Header(default="", alias="X-Telegram-Init-Data"),
    session: AsyncSession = Depends(get_async_session),
) -> User:
    if not x_telegram_init_data:
        raise HTTPException(status_code=401, detail="Missing X-Telegram-Init-Data header")
    settings = Settings()
    try:
        payload = validate_webapp_init_data(x_telegram_init_data, settings.telegram_bot_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    user = await get_user_by_telegram_id(session, payload.user_id)
    if not user:
        user = await get_or_create_user(session, payload.user_id)
    return user
