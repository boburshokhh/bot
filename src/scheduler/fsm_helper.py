"""Set FSM state from Celery (same Redis as app)."""
import asyncio
from datetime import date

from aiogram import Bot
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.redis import RedisStorage

from src.bot.states import PlanStates


def _get_bot_id(token: str) -> int:
    return int(token.split(":")[0])


async def set_awaiting_plan(redis_url: str, bot_token: str, telegram_id: int, plan_date: date) -> None:
    storage = RedisStorage.from_url(redis_url)
    bot_id = _get_bot_id(bot_token)
    key = StorageKey(bot_id=bot_id, chat_id=telegram_id, user_id=telegram_id)
    await storage.set_state(key, PlanStates.awaiting_plan)
    await storage.set_data(key, {"plan_date": plan_date.isoformat()})
    await storage.close()


async def set_awaiting_confirmation(
    redis_url: str, bot_token: str, telegram_id: int, plan_id: int, plan_date: date, user_id: int
) -> None:
    storage = RedisStorage.from_url(redis_url)
    bot_id = _get_bot_id(bot_token)
    key = StorageKey(bot_id=bot_id, chat_id=telegram_id, user_id=telegram_id)
    await storage.set_state(key, PlanStates.awaiting_confirmation)
    await storage.set_data(key, {
        "plan_id": plan_id,
        "plan_date": plan_date.isoformat(),
        "user_id": user_id,
    })
    await storage.close()


def run_async(coro):
    return asyncio.run(coro)
