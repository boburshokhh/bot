"""Start and timezone selection."""
import logging
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo
import re

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
import json

from src.bot.keyboards import main_menu_keyboard, tz_keyboard, webapp_keyboard, morning_reply_keyboard, evening_inline_keyboard
from src.bot.states import MenuStates, OnboardingStates
from src.bot.text import (
    COMMANDS_OVERVIEW, TIMEZONE_CHOOSE_PROMPT, WELCOME, format_settings, format_tz_set,
    MORNING_PROMPT, TEST_MORNING_SENT, TEST_EVENING_SENT, TEST_DELIVERY_ERROR, format_evening_plan
)
from src.bot.user_flow import get_user_or_run_onboarding
from src.config import Settings
from src.db.models import NotificationLog
from src.scheduler.tasks import _get_dispatch_window, send_evening_prompt, send_morning_prompt
from src.services.notifications import TYPE_EVENING, TYPE_MORNING, STATUS_SENT
from src.services.plan import get_plan_for_date
from src.services.user import (
    get_or_create_user,
    get_user_by_telegram_id,
    update_morning_reminder_settings,
    update_notify_times,
    update_user_timezone,
    update_onboarding_flags,
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
async def cmd_start(message: Message, session: AsyncSession, state: FSMContext):
    user_id = message.from_user.id if message.from_user else None
    if user_id is None:
        logger.warning("cmd_start: message.from_user is None")
        await message.answer("Не удалось определить пользователя. Напишите боту в личные сообщения.")
        return
    if getattr(message.from_user, "is_bot", False):
        logger.warning("cmd_start: bot account tried to start, telegram_id=%s", user_id)
        await message.answer("Боты не могут пользоваться этим ботом. Используйте личный аккаунт.")
        return
    logger.info("cmd_start: user_id=%s", user_id)
    try:
        user = await get_user_or_run_onboarding(session, user_id, message, state)
        if user:
            await state.set_state(MenuStates.main)
            await message.answer("Главное меню:", reply_markup=main_menu_keyboard())
            webapp_url = _build_webapp_url()
            if webapp_url:
                await message.answer("Открыть панель управления:", reply_markup=webapp_keyboard(webapp_url))
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
async def cmd_start_button(message: Message, session: AsyncSession, state: FSMContext):
    """Handle Start/Запустить button (some clients send text without slash)."""
    await cmd_start(message, session, state)


@router.message(Command("time"))
async def cmd_time(message: Message, session: AsyncSession):
    """Show bot server time (UTC) and user's local time for debugging."""
    utc_now = datetime.now(timezone.utc)
    telegram_id = message.from_user.id if message.from_user else None
    lines = [
        f"🕐 Время сервера бота (UTC): {utc_now.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Unix (сек): {int(utc_now.timestamp())}",
        f"Твой Telegram ID (from_user.id): {telegram_id}",
    ]
    user = await get_user_by_telegram_id(session, telegram_id) if telegram_id is not None else None
    if user:
        lines.append(f"В БД: user.id={user.id}, telegram_id={user.telegram_id} (должен совпадать с твоим Telegram ID)")
        try:
            tz = ZoneInfo(user.timezone)
            local_now = utc_now.astimezone(tz)
            lines.append(f"Твоё время ({user.timezone}): {local_now.strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append(f"Уведомления: утро {user.notify_morning_time.strftime('%H:%M')}, вечер {user.notify_evening_time.strftime('%H:%M')}")
        except Exception:
            lines.append("(часовой пояс не определён)")
    else:
        lines.append("В БД пользователь не найден — напиши /start")
    await message.answer("\n".join(lines))


@router.message(Command("me"))
async def cmd_me(message: Message, session: AsyncSession):
    """Show your Telegram ID and DB user record for diagnostics (e.g. compare with notification_log.user_id)."""
    telegram_id = message.from_user.id if message.from_user else None
    if telegram_id is None:
        await message.answer("Не удалось определить Telegram ID.")
        return
    user = await get_user_by_telegram_id(session, telegram_id)
    lines = [
        f"Твой Telegram ID: {telegram_id}",
        f"В БД: user.id={user.id}, telegram_id={user.telegram_id}" if user else "В БД пользователь не найден.",
    ]
    if user:
        lines.append(f"Часовой пояс: {user.timezone}")
        lines.append(f"Утро: {user.notify_morning_time.strftime('%H:%M')}, вечер: {user.notify_evening_time.strftime('%H:%M')}")
    await message.answer("\n".join(lines))


@router.message(Command("check_cron"))
async def cmd_check_cron(message: Message, session: AsyncSession):
    """Show how many minutes until next morning/evening notification and confirm settings are saved."""
    user = await get_user_by_telegram_id(session, message.from_user.id)
    if not user:
        await message.answer("Сначала выбери часовой пояс — напиши /start")
        return

    try:
        tz = ZoneInfo(user.timezone)
    except Exception:
        await message.answer("Часовой пояс не определён. Используй /timezone для смены.")
        return

    utc_now = datetime.now(timezone.utc)
    local_now = utc_now.astimezone(tz)
    now_m = local_now.hour * 60 + local_now.minute
    window = _get_dispatch_window()

    def _minutes_until(target_time) -> int:
        target_m = target_time.hour * 60 + target_time.minute
        diff = (target_m - now_m) % 1440
        return diff

    lines = [
        f"Сейчас твоё время: {local_now.strftime('%H:%M')} ({user.timezone})",
        f"Время сервера (UTC): {utc_now.strftime('%H:%M:%S')}",
        "",
        f"Утреннее уведомление: {user.notify_morning_time.strftime('%H:%M')} — через {_minutes_until(user.notify_morning_time)} мин",
        f"Вечернее уведомление: {user.notify_evening_time.strftime('%H:%M')} — через {_minutes_until(user.notify_evening_time)} мин",
        f"Интервал повторов: каждые {user.morning_reminder_interval_minutes} мин, макс {user.morning_reminder_max_attempts} раз",
        f"Окно отправки (DISPATCH_WINDOW_MINUTES): {window} мин",
        "",
        "Если уведомления не приходят — проверь на сервере:",
        "  docker compose logs celery_beat --tail=20",
        "  docker compose logs celery_worker --tail=30",
        "В логах beat должны быть строки «dispatch_daily_notifications»,",
        "в логах worker — «Dispatching morning/evening prompt».",
    ]
    await message.answer("\n".join(lines))


@router.message(Command("test_morning"))
async def cmd_test_morning(message: Message, session: AsyncSession):
    user = await get_user_by_telegram_id(session, message.from_user.id)
    if not user:
        await message.answer("Сначала выбери часовой пояс — напиши /start")
        return

    try:
        ZoneInfo(user.timezone)
    except Exception:
        await message.answer("Часовой пояс не определён. Используй /timezone для смены.")
        return

    await message.answer("Отправляю тестовое утреннее сообщение...")
    try:
        await message.answer(
            MORNING_PROMPT,
            reply_markup=morning_reply_keyboard(),
        )
        await message.answer(TEST_MORNING_SENT)
    except Exception as e:
        logger.exception("Test morning delivery failed: %s", e)
        await message.answer(TEST_DELIVERY_ERROR.format(error=str(e)))


@router.message(Command("test_evening"))
async def cmd_test_evening(message: Message, session: AsyncSession):
    user = await get_user_by_telegram_id(session, message.from_user.id)
    if not user:
        await message.answer("Сначала выбери часовой пояс — напиши /start")
        return

    try:
        tz = ZoneInfo(user.timezone)
    except Exception:
        await message.answer("Часовой пояс не определён. Используй /timezone для смены.")
        return

    local_now = datetime.now(timezone.utc).astimezone(tz)
    plan_date = local_now.date()
    plan = await get_plan_for_date(session, user.id, plan_date)

    await message.answer("Отправляю тестовое вечернее сообщение...")
    try:
        if not plan or not plan.tasks:
            await message.answer("План на сегодня не найден. Создай план утром.")
        else:
            tasks_with_status = [
                (t.text, t.status.status_enum if t.status else None)
                for t in sorted(plan.tasks, key=lambda x: x.position)
            ]
            text = format_evening_plan(plan_date, tasks_with_status)
            tasks_kb = [(t.id, t.status.status_enum if t.status else None) for t in sorted(plan.tasks, key=lambda x: x.position)]
            await message.answer(
                text,
                reply_markup=evening_inline_keyboard(tasks_kb),
            )
        await message.answer(TEST_EVENING_SENT)
    except Exception as e:
        logger.exception("Test evening delivery failed: %s", e)
        await message.answer(TEST_DELIVERY_ERROR.format(error=str(e)))


@router.message(Command("retry_evening"))
async def cmd_retry_evening(message: Message, session: AsyncSession):
    """Снять блокировку «уже отправлено» за сегодня и отправить вечернее уведомление сейчас (без ручного DELETE в БД)."""
    user = await get_user_by_telegram_id(session, message.from_user.id)
    if not user:
        await message.answer("Сначала выбери часовой пояс — напиши /start")
        return
    try:
        tz = ZoneInfo(user.timezone)
    except Exception:
        await message.answer("Часовой пояс не определён. Используй /timezone для смены.")
        return
    user_today = datetime.now(timezone.utc).astimezone(tz).date()
    await session.execute(
        delete(NotificationLog).where(
            NotificationLog.user_id == user.id,
            NotificationLog.type == TYPE_EVENING,
            NotificationLog.status == STATUS_SENT,
            NotificationLog.payload["date"].astext == user_today.isoformat(),
        )
    )
    await session.commit()
    send_evening_prompt.delay(user.id, user_today.isoformat(), 0)
    await message.answer("Задача отправки вечернего уведомления поставлена в очередь. Сообщение придёт в течение минуты.")


@router.message(Command("retry_morning"))
async def cmd_retry_morning(message: Message, session: AsyncSession):
    """Снять блокировку «уже отправлено» за сегодня и отправить утреннее уведомление сейчас (без ручного DELETE в БД)."""
    user = await get_user_by_telegram_id(session, message.from_user.id)
    if not user:
        await message.answer("Сначала выбери часовой пояс — напиши /start")
        return
    try:
        tz = ZoneInfo(user.timezone)
    except Exception:
        await message.answer("Часовой пояс не определён. Используй /timezone для смены.")
        return
    user_today = datetime.now(timezone.utc).astimezone(tz).date()
    await session.execute(
        delete(NotificationLog).where(
            NotificationLog.user_id == user.id,
            NotificationLog.type == TYPE_MORNING,
            NotificationLog.status == STATUS_SENT,
            NotificationLog.payload["date"].astext == user_today.isoformat(),
        )
    )
    await session.commit()
    send_morning_prompt.delay(user.id, user_today.isoformat(), 0)
    await message.answer("Задача отправки утреннего уведомления поставлена в очередь. Сообщение придёт в течение минуты.")


@router.message(Command("help"))
@router.message(Command("commands"))
async def cmd_help(message: Message):
    await message.answer(COMMANDS_OVERVIEW)


@router.message(Command("settings"))
async def cmd_settings(message: Message, session: AsyncSession, state: FSMContext):
    user = await get_user_or_run_onboarding(session, message.from_user.id, message, state)
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
async def cmd_timezone(message: Message, session: AsyncSession, state: FSMContext):
    user = await get_user_or_run_onboarding(session, message.from_user.id, message, state)
    if not user:
        return
    await message.answer(TIMEZONE_CHOOSE_PROMPT, reply_markup=tz_keyboard(include_detect=True))


@router.message(Command("set_morning"))
async def cmd_set_morning(message: Message, session: AsyncSession, state: FSMContext):
    user = await get_user_or_run_onboarding(session, message.from_user.id, message, state)
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
async def cmd_set_evening(message: Message, session: AsyncSession, state: FSMContext):
    user = await get_user_or_run_onboarding(session, message.from_user.id, message, state)
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
async def cmd_set_interval(message: Message, session: AsyncSession, state: FSMContext):
    user = await get_user_or_run_onboarding(session, message.from_user.id, message, state)
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
async def cmd_set_attempts(message: Message, session: AsyncSession, state: FSMContext):
    user = await get_user_or_run_onboarding(session, message.from_user.id, message, state)
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
async def cmd_webapp(message: Message, session: AsyncSession, state: FSMContext):
    user = await get_user_or_run_onboarding(session, message.from_user.id, message, state)
    if not user:
        return
    webapp_url = _build_webapp_url()
    if not webapp_url:
        await message.answer("WEBHOOK_BASE_URL не настроен. Веб-панель пока недоступна.")
        return
    await message.answer("Открыть веб-панель управления:", reply_markup=webapp_keyboard(webapp_url))


@router.message(OnboardingStates.awaiting_timezone, F.text.in_(ALLOWED_TZ))
@router.message(F.text.in_(ALLOWED_TZ))
async def set_timezone(message: Message, session: AsyncSession, state: FSMContext):
    tz = message.text.strip()
    user = await get_user_by_telegram_id(session, message.from_user.id)
    if not user:
        user = await get_or_create_user(session, message.from_user.id, timezone=tz)
    else:
        await update_user_timezone(session, user.id, tz)
    await update_onboarding_flags(session, user.id, tz_confirmed=True)
    await message.answer(format_tz_set(user.notify_morning_time), reply_markup=ReplyKeyboardRemove())
    await get_user_or_run_onboarding(session, message.from_user.id, message, state)


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
            await update_onboarding_flags(session, user.id, tz_confirmed=True)
            await message.answer(f"✅ Часовой пояс сохранён: {tz}", reply_markup=ReplyKeyboardRemove())
            await get_user_or_run_onboarding(session, message.from_user.id, message, state)
        else:
            await message.answer("❌ Неизвестные данные из WebApp")
    except json.JSONDecodeError:
        await message.answer("❌ Ошибка обработки данных из WebApp")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")


@router.message(OnboardingStates.awaiting_morning_time, F.text)
async def onboarding_morning_time(message: Message, session: AsyncSession, state: FSMContext):
    text = (message.text or "").strip()
    user = await get_user_by_telegram_id(session, message.from_user.id)
    if not user:
        return
    
    if text.startswith("Оставить "):
        text = text.replace("Оставить ", "").strip()
    
    t = _parse_hhmm(text)
    if not t:
        await message.answer("Неверный формат. Введите HH:MM (например 07:30) или нажмите кнопку.")
        return
    
    await update_notify_times(session, user.id, notify_morning_time=t)
    await update_onboarding_flags(session, user.id, morning_confirmed=True)
    await message.answer(f"Утреннее время сохранено: {t.strftime('%H:%M')}", reply_markup=ReplyKeyboardRemove())
    await get_user_or_run_onboarding(session, message.from_user.id, message, state)


@router.message(OnboardingStates.awaiting_evening_time, F.text)
async def onboarding_evening_time(message: Message, session: AsyncSession, state: FSMContext):
    text = (message.text or "").strip()
    user = await get_user_by_telegram_id(session, message.from_user.id)
    if not user:
        return
    
    if text.startswith("Оставить "):
        text = text.replace("Оставить ", "").strip()
    
    t = _parse_hhmm(text)
    if not t:
        await message.answer("Неверный формат. Введите HH:MM (например 21:30) или нажмите кнопку.")
        return
    
    await update_notify_times(session, user.id, notify_evening_time=t)
    await update_onboarding_flags(session, user.id, evening_confirmed=True)
    await message.answer(f"Вечернее время сохранено: {t.strftime('%H:%M')}", reply_markup=ReplyKeyboardRemove())
    
    # After evening, onboarding is fully confirmed
    user = await get_user_or_run_onboarding(session, message.from_user.id, message, state)
    if user:
        await state.set_state(MenuStates.main)
        await message.answer("Настройка завершена! Добро пожаловать. Выберите раздел:", reply_markup=main_menu_keyboard())
        webapp_url = _build_webapp_url()
        if webapp_url:
            await message.answer("Открыть панель управления:", reply_markup=webapp_keyboard(webapp_url))
