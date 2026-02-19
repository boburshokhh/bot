"""
Режим long polling: бот сам запрашивает обновления у Telegram.
Подходит для сервера без белого IP — webhook и домен не нужны.
Запуск: python -m src.run_polling
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage

from src.config import Settings
from src.db import init_async_engine, set_async_session_factory
from src.bot.handlers import router as bot_router
from src.bot.middlewares import DbSessionMiddleware, RequestIdMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_bot_and_dp():
    settings = Settings()
    storage = RedisStorage.from_url(settings.redis_url)
    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher(storage=storage)
    dp.message.middleware(DbSessionMiddleware())
    dp.message.middleware(RequestIdMiddleware())
    dp.callback_query.middleware(DbSessionMiddleware())
    dp.callback_query.middleware(RequestIdMiddleware())
    dp.include_router(bot_router)
    return bot, dp


async def main():
    settings = Settings()
    engine = init_async_engine(settings.database_url)
    set_async_session_factory(engine)

    bot, dp = create_bot_and_dp()

    # Удаляем webhook, если был — иначе Telegram не отдаст обновления в polling
    await bot.delete_webhook(drop_pending_updates=True)

    try:
        logger.info("Long polling started (no webhook needed)")
        await dp.start_polling(bot)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
