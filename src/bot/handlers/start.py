"""Start and timezone selection."""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards import tz_keyboard
from src.bot.text import COMMANDS_OVERVIEW, TIMEZONE_CHOOSE_PROMPT, WELCOME, TZ_SET, format_settings
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
    await get_or_create_user(session, message.from_user.id)
    await message.answer(WELCOME, reply_markup=tz_keyboard())


@router.message(Command("help"))
@router.message(Command("commands"))
async def cmd_help(message: Message):
    await message.answer(COMMANDS_OVERVIEW)


@router.message(Command("settings"))
async def cmd_settings(message: Message, session: AsyncSession):
    user = await get_user_by_telegram_id(session, message.from_user.id)
    if not user:
        await message.answer("Сначала отправь /start и выбери часовой пояс.")
        return
    await message.answer(
        format_settings(
            user.timezone,
            user.notify_morning_time,
            user.notify_evening_time,
        )
    )


@router.message(Command("timezone"))
async def cmd_timezone(message: Message, session: AsyncSession):
    user = await get_user_by_telegram_id(session, message.from_user.id)
    if not user:
        await message.answer("Сначала отправь /start и выбери часовой пояс.")
        return
    await message.answer(TIMEZONE_CHOOSE_PROMPT, reply_markup=tz_keyboard())


@router.message(F.text.in_(ALLOWED_TZ))
async def set_timezone(message: Message, session: AsyncSession):
    tz = message.text.strip()
    user = await get_user_by_telegram_id(session, message.from_user.id)
    if not user:
        user = await get_or_create_user(session, message.from_user.id, timezone=tz)
    else:
        await update_user_timezone(session, user.id, tz)
    await message.answer(f"{TZ_SET}\n\n{COMMANDS_OVERVIEW}", reply_markup=None)
