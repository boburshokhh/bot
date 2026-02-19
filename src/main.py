"""FastAPI app and webhook entry for the planning bot."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.api import webapp_api_router
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
PROJECT_ROOT = Path(__file__).resolve().parents[1]
app.mount("/static", StaticFiles(directory=str(PROJECT_ROOT / "static")), name="static")
app.include_router(webapp_api_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/webapp")
async def webapp():
    return FileResponse(PROJECT_ROOT / "templates" / "webapp.html")


async def _process_update(body: dict) -> None:
    """Process update in background (log errors, do not fail webhook response)."""
    try:
        from aiogram.types import Update
        update = Update.model_validate(body)
        await dp.feed_webhook_update(bot, update)
    except Exception as e:
        logger.exception("Webhook processing error: %s", e)


async def _handle_webhook(request: Request) -> JSONResponse | dict:
    logger.info("Webhook request received")
    settings = Settings()
    if settings.webhook_secret:
        secret_header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if secret_header != settings.webhook_secret:
            return JSONResponse(status_code=403, content={"ok": False})
    try:
        body = await request.json()
    except Exception as e:
        logger.exception("Webhook body error: %s", e)
        return JSONResponse(status_code=400, content={"ok": False, "error": str(e)})
    # Return 200 immediately so Telegram does not retry; process in background
    import asyncio
    asyncio.create_task(_process_update(body))
    return {"ok": True}


@app.post("/webhook")
@app.post("/webhook/")
async def webhook(request: Request):
    return await _handle_webhook(request)
