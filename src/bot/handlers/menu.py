"""Reply keyboard menu navigation after timezone selection."""

from datetime import datetime, time, timezone
import re
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards import (
    BTN_DELETE_PLAN,
    BTN_HELP,
    BTN_HISTORY,
    BTN_NAV_BACK,
    BTN_NAV_MAIN,
    BTN_PLAN,
    BTN_PLAN_ADD,
    BTN_RESET_NOTIFICATIONS,
    BTN_SETTINGS,
    BTN_SETTINGS_INTERVALS,
    BTN_SETTINGS_NOTIFY,
    BTN_SETTINGS_TZ,
    BTN_SET_ATTEMPTS,
    BTN_SET_EVENING,
    BTN_SET_INTERVAL,
    BTN_SET_MORNING,
    BTN_STATS,
    BTN_STATS_OVERVIEW,
    BTN_TODAY,
    intervals_submenu_keyboard,
    main_menu_keyboard,
    notify_time_submenu_keyboard,
    plan_submenu_keyboard,
    settings_submenu_keyboard,
    stats_submenu_keyboard,
    tz_keyboard,
)
from src.bot.text import COMMANDS_OVERVIEW, TIMEZONE_CHOOSE_PROMPT
from src.bot.states import MenuStates, SettingsStates
from src.bot.user_flow import get_user_or_run_onboarding
from src.db.models import NotificationLog
from src.services.notifications import TYPE_EVENING, TYPE_MORNING, STATUS_SENT
from src.services.user import (
    update_morning_reminder_settings,
    update_notify_times,
)

router = Router()


def _parse_hhmm(value: str) -> time | None:
    if not re.fullmatch(r"\d{2}:\d{2}", value):
        return None
    hour, minute = value.split(":")
    h = int(hour)
    m = int(minute)
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return None
    return time(h, m)


async def _go_main(message: Message, state: FSMContext):
    await state.set_state(MenuStates.main)
    await message.answer("Главное меню:", reply_markup=main_menu_keyboard())


# --- Main menu (MenuStates.main) ---
@router.message(MenuStates.main, F.text == BTN_PLAN)
async def menu_plan(message: Message, state: FSMContext):
    await state.set_state(MenuStates.plan)
    await message.answer("Меню «План»:", reply_markup=plan_submenu_keyboard())


@router.message(MenuStates.main, F.text == BTN_STATS)
async def menu_stats(message: Message, state: FSMContext):
    await state.set_state(MenuStates.stats)
    await message.answer("Меню «Статистика»:", reply_markup=stats_submenu_keyboard())


@router.message(MenuStates.main, F.text == BTN_SETTINGS)
async def menu_settings(message: Message, state: FSMContext):
    await state.set_state(MenuStates.settings)
    await message.answer("Меню «Настройки»:", reply_markup=settings_submenu_keyboard())


@router.message(MenuStates.main, F.text == BTN_HELP)
async def action_help_main(message: Message):
    await message.answer(COMMANDS_OVERVIEW)


# --- Plan submenu (MenuStates.plan) ---
@router.message(MenuStates.plan, F.text == BTN_NAV_BACK)
@router.message(MenuStates.plan, F.text == BTN_NAV_MAIN)
async def plan_nav_back(message: Message, state: FSMContext):
    await _go_main(message, state)


@router.message(MenuStates.plan, F.text == BTN_PLAN_ADD)
async def action_plan_add(message: Message, session: AsyncSession, state: FSMContext):
    from src.bot.handlers.plan import cmd_plan
    await cmd_plan(message, session, state)


@router.message(MenuStates.plan, F.text == BTN_TODAY)
async def action_today_plan(message: Message, session: AsyncSession):
    from src.bot.handlers.stats import cmd_today
    await cmd_today(message, session)


@router.message(MenuStates.plan, F.text == BTN_DELETE_PLAN)
async def action_delete_plan(message: Message, session: AsyncSession, state: FSMContext):
    from src.bot.handlers.plan import cmd_delete_plan
    await cmd_delete_plan(message, session, state)


@router.message(MenuStates.plan, F.text == BTN_HISTORY)
async def action_history_plan(message: Message):
    await message.answer("Использование: /history YYYY-MM (например /history 2025-01)")


# --- Stats submenu (MenuStates.stats) ---
@router.message(MenuStates.stats, F.text == BTN_NAV_BACK)
@router.message(MenuStates.stats, F.text == BTN_NAV_MAIN)
async def stats_nav_back(message: Message, state: FSMContext):
    await _go_main(message, state)


@router.message(MenuStates.stats, F.text == BTN_STATS_OVERVIEW)
async def action_stats(message: Message, session: AsyncSession):
    from src.bot.handlers.stats import cmd_stats
    await cmd_stats(message, session)


@router.message(MenuStates.stats, F.text == BTN_TODAY)
async def action_today_stats(message: Message, session: AsyncSession):
    from src.bot.handlers.stats import cmd_today
    await cmd_today(message, session)


@router.message(MenuStates.stats, F.text == BTN_HISTORY)
async def action_history_stats(message: Message):
    await message.answer("Использование: /history YYYY-MM (например /history 2025-01)")


# --- Settings submenu (MenuStates.settings) ---
@router.message(MenuStates.settings, F.text == BTN_NAV_BACK)
@router.message(MenuStates.settings, F.text == BTN_NAV_MAIN)
async def settings_nav_back(message: Message, state: FSMContext):
    await _go_main(message, state)


@router.message(MenuStates.settings, F.text == BTN_SETTINGS_TZ)
async def action_settings_timezone(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(TIMEZONE_CHOOSE_PROMPT, reply_markup=tz_keyboard(include_detect=True))


@router.message(MenuStates.settings, F.text == BTN_SETTINGS_NOTIFY)
async def menu_settings_notify(message: Message, state: FSMContext):
    await state.set_state(MenuStates.settings_notify)
    await message.answer(
        "Настройки → Время уведомлений:",
        reply_markup=notify_time_submenu_keyboard(),
    )


@router.message(MenuStates.settings, F.text == BTN_SETTINGS_INTERVALS)
async def menu_settings_intervals(message: Message, state: FSMContext):
    await state.set_state(MenuStates.settings_intervals)
    await message.answer(
        "Настройки → Интервалы:",
        reply_markup=intervals_submenu_keyboard(),
    )


@router.message(MenuStates.settings, F.text == BTN_RESET_NOTIFICATIONS)
async def action_reset_notifications(message: Message, session: AsyncSession):
    """Сбросить записи «уже отправлено» за сегодня. Время уведомлений не меняется, повторная отправка — по расписанию."""
    user = await get_user_or_run_onboarding(session, message.from_user.id, message, state)
    if not user:
        return
    try:
        tz = ZoneInfo(user.timezone)
    except Exception:
        await message.answer("Часовой пояс не определён. Используй /timezone для смены.")
        return
    user_today = datetime.now(timezone.utc).astimezone(tz).date()
    today_iso = user_today.isoformat()
    for ntype in (TYPE_MORNING, TYPE_EVENING):
        await session.execute(
            delete(NotificationLog).where(
                NotificationLog.user_id == user.id,
                NotificationLog.type == ntype,
                NotificationLog.status == STATUS_SENT,
                NotificationLog.payload["date"].astext == today_iso,
            )
        )
    await session.commit()
    await message.answer(
        "Сбросил записи об отправке за сегодня. Время уведомлений не изменилось — утро и вечер придут в настроенное время."
    )


# --- Settings notify submenu (MenuStates.settings_notify) ---
@router.message(MenuStates.settings_notify, F.text == BTN_NAV_BACK)
@router.message(MenuStates.settings_notify, F.text == BTN_NAV_MAIN)
async def settings_notify_nav_back(message: Message, state: FSMContext):
    await state.set_state(MenuStates.settings)
    await message.answer("Меню «Настройки»:", reply_markup=settings_submenu_keyboard())


@router.message(MenuStates.settings_notify, F.text == BTN_SET_MORNING)
async def action_settings_set_morning(message: Message, state: FSMContext):
    await state.set_state(SettingsStates.awaiting_morning_time)
    await message.answer("Введите утреннее время в формате HH:MM (например 07:30):")


@router.message(MenuStates.settings_notify, F.text == BTN_SET_EVENING)
async def action_settings_set_evening(message: Message, state: FSMContext):
    await state.set_state(SettingsStates.awaiting_evening_time)
    await message.answer("Введите вечернее время в формате HH:MM (например 21:30):")


# --- Settings intervals submenu (MenuStates.settings_intervals) ---
@router.message(MenuStates.settings_intervals, F.text == BTN_NAV_BACK)
@router.message(MenuStates.settings_intervals, F.text == BTN_NAV_MAIN)
async def settings_intervals_nav_back(message: Message, state: FSMContext):
    await state.set_state(MenuStates.settings)
    await message.answer("Меню «Настройки»:", reply_markup=settings_submenu_keyboard())


@router.message(MenuStates.settings_intervals, F.text == BTN_SET_INTERVAL)
async def action_settings_set_interval(message: Message, state: FSMContext):
    await state.set_state(SettingsStates.awaiting_interval_minutes)
    await message.answer("Введите интервал повторов в минутах (5-720), например 45:")


@router.message(MenuStates.settings_intervals, F.text == BTN_SET_ATTEMPTS)
async def action_settings_set_attempts(message: Message, state: FSMContext):
    await state.set_state(SettingsStates.awaiting_max_attempts)
    await message.answer("Введите максимум повторных напоминаний (0-10), например 2:")


# --- Settings value handlers (after prompting for input) ---
# Не перехватываем команды (/) — пусть обрабатывают start/stats/plan и т.д.
@router.message(SettingsStates.awaiting_morning_time, F.text, ~F.text.startswith("/"))
async def receive_morning_time(message: Message, session: AsyncSession, state: FSMContext):
    t = _parse_hhmm((message.text or "").strip())
    if not t:
        await message.answer("Неверный формат. Введите HH:MM (например 07:30).")
        return
    user = await get_user_or_run_onboarding(session, message.from_user.id, message, state)
    if not user:
        return
    await update_notify_times(session, user.id, notify_morning_time=t)
    await state.clear()
    await state.set_state(MenuStates.settings_notify)
    await message.answer(
        f"Утреннее время обновлено: {t.strftime('%H:%M')}",
        reply_markup=notify_time_submenu_keyboard(),
    )


@router.message(SettingsStates.awaiting_evening_time, F.text, ~F.text.startswith("/"))
async def receive_evening_time(message: Message, session: AsyncSession, state: FSMContext):
    t = _parse_hhmm((message.text or "").strip())
    if not t:
        await message.answer("Неверный формат. Введите HH:MM (например 21:30).")
        return
    user = await get_user_or_run_onboarding(session, message.from_user.id, message, state)
    if not user:
        return
    await update_notify_times(session, user.id, notify_evening_time=t)
    await state.clear()
    await state.set_state(MenuStates.settings_notify)
    await message.answer(
        f"Вечернее время обновлено: {t.strftime('%H:%M')}",
        reply_markup=notify_time_submenu_keyboard(),
    )


@router.message(SettingsStates.awaiting_interval_minutes, F.text, ~F.text.startswith("/"))
async def receive_interval_minutes(message: Message, session: AsyncSession, state: FSMContext):
    value = (message.text or "").strip()
    if not value.isdigit():
        await message.answer("Введите число (минуты), например 45.")
        return
    minutes = int(value)
    if not (5 <= minutes <= 720):
        await message.answer("Интервал должен быть в диапазоне 5-720 минут.")
        return
    user = await get_user_or_run_onboarding(session, message.from_user.id, message, state)
    if not user:
        return
    await update_morning_reminder_settings(session, user.id, interval_minutes=minutes)
    await state.clear()
    await state.set_state(MenuStates.settings_intervals)
    await message.answer(
        f"Интервал повторных напоминаний: {minutes} мин.",
        reply_markup=intervals_submenu_keyboard(),
    )


@router.message(SettingsStates.awaiting_max_attempts, F.text, ~F.text.startswith("/"))
async def receive_max_attempts(message: Message, session: AsyncSession, state: FSMContext):
    value = (message.text or "").strip()
    if not value.isdigit():
        await message.answer("Введите число (0-10), например 2.")
        return
    attempts = int(value)
    if not (0 <= attempts <= 10):
        await message.answer("Количество повторов должно быть в диапазоне 0-10.")
        return
    user = await get_user_or_run_onboarding(session, message.from_user.id, message, state)
    if not user:
        return
    await update_morning_reminder_settings(session, user.id, max_attempts=attempts)
    await state.clear()
    await state.set_state(MenuStates.settings_intervals)
    await message.answer(
        f"Максимум повторных утренних напоминаний: {attempts}.",
        reply_markup=intervals_submenu_keyboard(),
    )
