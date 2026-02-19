"""Start and timezone selection."""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards import tz_keyboard
from src.bot.text import WELCOME, TZ_SET
from src.services.user import get_or_create_user, get_user_by_telegram_id, update_user_timezone

router = Router()

# Valid IANA timezones we offer (subset)
ALLOWED_TZ = {
    "Europe/Moscow", "Europe/Kyiv", "Europe/Minsk",
    "Europe/London", "Europe/Berlin", "Asia/Almaty",
    "Asia/Tbilisi", "Asia/Yerevan", "Asia/Tashkent",
    "UTC",
}


@router.message(Command("start"))
async def cmd_start(message: Message, session: AsyncSession):
    user = await get_or_create_user(session, message.from_user.id)
    await message.answer(WELCOME, reply_markup=tz_keyboard())


@router.message(F.text.in_(ALLOWED_TZ))
async def set_timezone(message: Message, session: AsyncSession):
    tz = message.text.strip()
    user = await get_user_by_telegram_id(session, message.from_user.id)
    if not user:
        user = await get_or_create_user(session, message.from_user.id, timezone=tz)
    else:
        await update_user_timezone(session, user.id, tz)
    await message.answer(TZ_SET, reply_markup=None)
