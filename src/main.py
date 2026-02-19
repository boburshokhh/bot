"""FastAPI app and webhook entry for the planning bot."""
import logging
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    engine = init_async_engine(settings.database_url)
    set_async_session_factory(engine)
    yield
    await engine.dispose()


app = FastAPI(title="Planning Bot", lifespan=lifespan)
bot, dp = create_bot_and_dp()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/webhook")
async def webhook(request: Request, response: Response):
    settings = Settings()
    if settings.webhook_secret:
        secret_header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if secret_header != settings.webhook_secret:
            return JSONResponse(status_code=403, content={"ok": False})
    try:
        body = await request.json()
        from aiogram.types import Update
        update = Update.model_validate(body)
        await dp.feed_webhook_update(bot, update)
    except Exception as e:
        logger.exception("Webhook error: %s", e)
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
    return {"ok": True}
