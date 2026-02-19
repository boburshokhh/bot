"""Start and timezone selection."""
import logging
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo
import re

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession
import json

from src.bot.keyboards import main_menu_keyboard, tz_keyboard, webapp_keyboard
from src.bot.states import MenuStates
from src.bot.text import COMMANDS_OVERVIEW, TIMEZONE_CHOOSE_PROMPT, WELCOME, TZ_SET, format_settings
from src.bot.user_flow import get_user_or_ask_timezone
from src.config import Settings
from src.services.user import (
    get_or_create_user,
    get_user_by_telegram_id,
    update_morning_reminder_settings,
    update_notify_times,
    update_user_timezone,
)

router = Router()
logger = logging.getLogger(__name__)

# Valid IANA timezones we offer (subset)
ALLOWED_TZ = {
    "Europe/Moscow", "Europe/Kyiv", "Europe/Minsk",
    "Europe/London", "Europe/Berlin", "Asia/Almaty",
    "Asia/Tbilisi", "Asia/Yerevan", "Asia/Tashkent",
    "UTC",
}


def _extract_command_arg(text: str | None) -> str:
    if not text:
        return ""
    parts = text.strip().split(maxsplit=1)
    if len(parts) < 2:
        return ""
    return parts[1].strip()


def _parse_hhmm(value: str) -> time | None:
    if not re.fullmatch(r"\d{2}:\d{2}", value):
        return None
    hour, minute = value.split(":")
    h = int(hour)
    m = int(minute)
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return None
    return time(h, m)


def _build_webapp_url() -> str | None:
    base = Settings().webhook_base_url.strip()
    if not base:
        return None
    return f"{base.rstrip('/')}/webapp"


@router.message(Command("start"))
async def cmd_start(message: Message, session: AsyncSession):
    user_id = message.from_user.id if message.from_user else None
    if user_id is None:
        logger.warning("cmd_start: message.from_user is None")
        await message.answer("Не удалось определить пользователя. Напишите боту в личные сообщения.")
        return
    logger.info("cmd_start: user_id=%s", user_id)
    try:
        await get_or_create_user(session, user_id)
        await message.answer(WELCOME, reply_markup=tz_keyboard(include_detect=True))
    except Exception as e:
        logger.exception("cmd_start failed: %s", e)
        try:
            await message.answer(
                "Произошла ошибка при запуске. Попробуйте ещё раз или напишите разработчику."
            )
        except Exception:
            pass
        raise


@router.message(F.text.in_({"Start", "Запустить", "start"}))
async def cmd_start_button(message: Message, session: AsyncSession):
    """Handle Start/Запустить button (some clients send text without slash)."""
    await cmd_start(message, session)


@router.message(Command("time"))
async def cmd_time(message: Message, session: AsyncSession):
    """Show bot server time (UTC) and user's local time for debugging."""
    utc_now = datetime.now(timezone.utc)
    lines = [
        f"🕐 Время сервера бота (UTC): {utc_now.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Unix (сек): {int(utc_now.timestamp())}",
    ]
    user = await get_user_by_telegram_id(session, message.from_user.id)
    if user:
        try:
            tz = ZoneInfo(user.timezone)
            local_now = utc_now.astimezone(tz)
            lines.append(f"Твоё время ({user.timezone}): {local_now.strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append(f"Уведомления: утро {user.notify_morning_time.strftime('%H:%M')}, вечер {user.notify_evening_time.strftime('%H:%M')}")
        except Exception:
            lines.append("(часовой пояс не определён)")
    await message.answer("\n".join(lines))


@router.message(Command("help"))
@router.message(Command("commands"))
async def cmd_help(message: Message):
    await message.answer(COMMANDS_OVERVIEW)


@router.message(Command("settings"))
async def cmd_settings(message: Message, session: AsyncSession):
    user = await get_user_or_ask_timezone(session, message.from_user.id, message)
    if not user:
        return
    await message.answer(
        format_settings(
            user.timezone,
            user.notify_morning_time,
            user.notify_evening_time,
            user.morning_reminder_interval_minutes,
            user.morning_reminder_max_attempts,
        )
    )
    webapp_url = _build_webapp_url()
    if webapp_url:
        await message.answer("Открыть панель управления:", reply_markup=webapp_keyboard(webapp_url))


@router.message(Command("timezone"))
async def cmd_timezone(message: Message, session: AsyncSession):
    user = await get_user_or_ask_timezone(session, message.from_user.id, message)
    if not user:
        return
    await message.answer(TIMEZONE_CHOOSE_PROMPT, reply_markup=tz_keyboard(include_detect=True))


@router.message(Command("set_morning"))
async def cmd_set_morning(message: Message, session: AsyncSession):
    user = await get_user_or_ask_timezone(session, message.from_user.id, message)
    if not user:
        return
    value = _extract_command_arg(message.text)
    t = _parse_hhmm(value)
    if not t:
        await message.answer("Использование: /set_morning HH:MM (например /set_morning 07:30)")
        return
    await update_notify_times(session, user.id, notify_morning_time=t)
    await message.answer(f"Утреннее время обновлено: {t.strftime('%H:%M')}")


@router.message(Command("set_evening"))
async def cmd_set_evening(message: Message, session: AsyncSession):
    user = await get_user_or_ask_timezone(session, message.from_user.id, message)
    if not user:
        return
    value = _extract_command_arg(message.text)
    t = _parse_hhmm(value)
    if not t:
        await message.answer("Использование: /set_evening HH:MM (например /set_evening 21:30)")
        return
    await update_notify_times(session, user.id, notify_evening_time=t)
    await message.answer(f"Вечернее время обновлено: {t.strftime('%H:%M')}")


@router.message(Command("set_interval"))
async def cmd_set_interval(message: Message, session: AsyncSession):
    user = await get_user_or_ask_timezone(session, message.from_user.id, message)
    if not user:
        return
    value = _extract_command_arg(message.text)
    if not value.isdigit():
        await message.answer("Использование: /set_interval MIN (например /set_interval 45)")
        return
    minutes = int(value)
    if not (5 <= minutes <= 720):
        await message.answer("Интервал должен быть в диапазоне 5-720 минут.")
        return
    await update_morning_reminder_settings(session, user.id, interval_minutes=minutes)
    await message.answer(f"Интервал повторных напоминаний: {minutes} мин.")


@router.message(Command("set_attempts"))
async def cmd_set_attempts(message: Message, session: AsyncSession):
    user = await get_user_or_ask_timezone(session, message.from_user.id, message)
    if not user:
        return
    value = _extract_command_arg(message.text)
    if not value.isdigit():
        await message.answer("Использование: /set_attempts N (например /set_attempts 2)")
        return
    attempts = int(value)
    if not (0 <= attempts <= 10):
        await message.answer("Количество повторов должно быть в диапазоне 0-10.")
        return
    await update_morning_reminder_settings(session, user.id, max_attempts=attempts)
    await message.answer(f"Максимум повторных утренних напоминаний: {attempts}.")


@router.message(Command("webapp"))
async def cmd_webapp(message: Message, session: AsyncSession):
    user = await get_user_or_ask_timezone(session, message.from_user.id, message)
    if not user:
        return
    webapp_url = _build_webapp_url()
    if not webapp_url:
        await message.answer("WEBHOOK_BASE_URL не настроен. Веб-панель пока недоступна.")
        return
    await message.answer("Открыть веб-панель управления:", reply_markup=webapp_keyboard(webapp_url))


@router.message(F.text.in_(ALLOWED_TZ))
async def set_timezone(message: Message, session: AsyncSession, state: FSMContext):
    tz = message.text.strip()
    user = await get_user_by_telegram_id(session, message.from_user.id)
    if not user:
        user = await get_or_create_user(session, message.from_user.id, timezone=tz)
    else:
        await update_user_timezone(session, user.id, tz)
    await message.answer(TZ_SET, reply_markup=ReplyKeyboardRemove())
    await state.set_state(MenuStates.main)
    await message.answer("Выберите раздел:", reply_markup=main_menu_keyboard())
    webapp_url = _build_webapp_url()
    if webapp_url:
        await message.answer("Открыть панель управления:", reply_markup=webapp_keyboard(webapp_url))


@router.message(F.web_app_data)
async def handle_webapp_data(message: Message, session: AsyncSession, state: FSMContext):
    """Handle data sent from WebApp (e.g., timezone detection)."""
    try:
        data = json.loads(message.web_app_data.data)
        if "timezone" in data:
            tz = data["timezone"].strip()
            # Validate timezone (can be any valid IANA timezone, not just from ALLOWED_TZ)
            try:
                ZoneInfo(tz)
            except Exception:
                await message.answer(f"❌ Неверный часовой пояс: {tz}")
                return

            user = await get_user_by_telegram_id(session, message.from_user.id)
            if not user:
                user = await get_or_create_user(session, message.from_user.id, timezone=tz)
            else:
                await update_user_timezone(session, user.id, tz)
            await message.answer(f"✅ Часовой пояс сохранён: {tz}")
            await state.set_state(MenuStates.main)
            await message.answer("Выберите раздел:", reply_markup=main_menu_keyboard())
            webapp_url = _build_webapp_url()
            if webapp_url:
                await message.answer("Открыть панель управления:", reply_markup=webapp_keyboard(webapp_url))
        else:
            await message.answer("❌ Неизвестные данные из WebApp")
    except json.JSONDecodeError:
        await message.answer("❌ Ошибка обработки данных из WebApp")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")
