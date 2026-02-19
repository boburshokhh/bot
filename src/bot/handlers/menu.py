"""Inline menu navigation after timezone selection."""

from datetime import time
import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards import (
    ACTION_HELP,
    ACTION_HISTORY,
    ACTION_PLAN_ADD,
    ACTION_SETTINGS_SET_ATTEMPTS,
    ACTION_SETTINGS_SET_EVENING,
    ACTION_SETTINGS_SET_INTERVAL,
    ACTION_SETTINGS_SET_MORNING,
    ACTION_SETTINGS_TIMEZONE,
    ACTION_STATS,
    ACTION_TODAY,
    MENU_MAIN,
    MENU_PLAN,
    MENU_SETTINGS,
    MENU_SETTINGS_INTERVALS,
    MENU_SETTINGS_NOTIFY,
    MENU_STATS,
    intervals_submenu_keyboard,
    main_menu_keyboard,
    notify_time_submenu_keyboard,
    plan_submenu_keyboard,
    settings_submenu_keyboard,
    stats_submenu_keyboard,
    tz_keyboard,
)
from src.bot.text import COMMANDS_OVERVIEW, TIMEZONE_CHOOSE_PROMPT
from src.bot.states import SettingsStates
from src.services.user import (
    get_user_by_telegram_id,
    update_morning_reminder_settings,
    update_notify_times,
)

router = Router()


async def _edit_menu(callback: CallbackQuery, *, title: str, reply_markup):
    await callback.answer()
    if not callback.message:
        return
    try:
        await callback.message.edit_text(title, reply_markup=reply_markup)
    except Exception:
        # Fallback if message can't be edited (e.g., too old / no text, etc.)
        await callback.message.answer(title, reply_markup=reply_markup)


def _parse_hhmm(value: str) -> time | None:
    if not re.fullmatch(r"\d{2}:\d{2}", value):
        return None
    hour, minute = value.split(":")
    h = int(hour)
    m = int(minute)
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return None
    return time(h, m)


@router.callback_query(F.data == MENU_MAIN)
async def menu_main(callback: CallbackQuery):
    await _edit_menu(callback, title="Главное меню:", reply_markup=main_menu_keyboard())


@router.callback_query(F.data == MENU_PLAN)
async def menu_plan(callback: CallbackQuery):
    await _edit_menu(callback, title="Меню «План»:",
                     reply_markup=plan_submenu_keyboard())


@router.callback_query(F.data == MENU_STATS)
async def menu_stats(callback: CallbackQuery):
    await _edit_menu(callback, title="Меню «Статистика»:",
                     reply_markup=stats_submenu_keyboard())


@router.callback_query(F.data == MENU_SETTINGS)
async def menu_settings(callback: CallbackQuery):
    await _edit_menu(callback, title="Меню «Настройки»:",
                     reply_markup=settings_submenu_keyboard())


@router.callback_query(F.data == MENU_SETTINGS_NOTIFY)
async def menu_settings_notify(callback: CallbackQuery):
    await _edit_menu(callback, title="Настройки → Время уведомлений:",
                     reply_markup=notify_time_submenu_keyboard())


@router.callback_query(F.data == MENU_SETTINGS_INTERVALS)
async def menu_settings_intervals(callback: CallbackQuery):
    await _edit_menu(callback, title="Настройки → Интервалы:",
                     reply_markup=intervals_submenu_keyboard())


@router.callback_query(F.data == ACTION_HELP)
async def action_help(callback: CallbackQuery):
    await callback.answer()
    if callback.message:
        await callback.message.answer(COMMANDS_OVERVIEW)


@router.callback_query(F.data == ACTION_PLAN_ADD)
async def action_plan_add(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    await callback.answer()
    if not callback.message:
        return
    # Reuse the existing /plan command handler.
    from src.bot.handlers.plan import cmd_plan

    await cmd_plan(callback.message, session, state)


@router.callback_query(F.data == ACTION_TODAY)
async def action_today(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    if not callback.message:
        return
    from src.bot.handlers.stats import cmd_today

    await cmd_today(callback.message, session)


@router.callback_query(F.data == ACTION_HISTORY)
async def action_history(callback: CallbackQuery):
    await callback.answer()
    if callback.message:
        await callback.message.answer("Использование: /history YYYY-MM (например /history 2025-01)")


@router.callback_query(F.data == ACTION_STATS)
async def action_stats(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    if not callback.message:
        return
    from src.bot.handlers.stats import cmd_stats

    await cmd_stats(callback.message, session)


@router.callback_query(F.data == ACTION_SETTINGS_TIMEZONE)
async def action_settings_timezone(callback: CallbackQuery):
    await callback.answer()
    if callback.message:
        # Switch back to reply-keyboard timezone picker.
        await callback.message.answer(TIMEZONE_CHOOSE_PROMPT, reply_markup=tz_keyboard(include_detect=True))


@router.callback_query(F.data == ACTION_SETTINGS_SET_MORNING)
async def action_settings_set_morning(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.message:
        await state.set_state(SettingsStates.awaiting_morning_time)
        await callback.message.answer("Введите утреннее время в формате HH:MM (например 07:30):")


@router.callback_query(F.data == ACTION_SETTINGS_SET_EVENING)
async def action_settings_set_evening(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.message:
        await state.set_state(SettingsStates.awaiting_evening_time)
        await callback.message.answer("Введите вечернее время в формате HH:MM (например 21:30):")


@router.callback_query(F.data == ACTION_SETTINGS_SET_INTERVAL)
async def action_settings_set_interval(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.message:
        await state.set_state(SettingsStates.awaiting_interval_minutes)
        await callback.message.answer("Введите интервал повторов в минутах (5-720), например 45:")


@router.callback_query(F.data == ACTION_SETTINGS_SET_ATTEMPTS)
async def action_settings_set_attempts(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.message:
        await state.set_state(SettingsStates.awaiting_max_attempts)
        await callback.message.answer("Введите максимум повторных напоминаний (0-10), например 2:")


@router.message(SettingsStates.awaiting_morning_time, F.text)
async def receive_morning_time(message: Message, session: AsyncSession, state: FSMContext):
    t = _parse_hhmm((message.text or "").strip())
    if not t:
        await message.answer("Неверный формат. Введите HH:MM (например 07:30).")
        return
    user = await get_user_by_telegram_id(session, message.from_user.id)
    if not user:
        await state.clear()
        await message.answer("Сначала отправь /start и выбери часовой пояс.")
        return
    await update_notify_times(session, user.id, notify_morning_time=t)
    await state.clear()
    await message.answer(f"Утреннее время обновлено: {t.strftime('%H:%M')}", reply_markup=settings_submenu_keyboard())


@router.message(SettingsStates.awaiting_evening_time, F.text)
async def receive_evening_time(message: Message, session: AsyncSession, state: FSMContext):
    t = _parse_hhmm((message.text or "").strip())
    if not t:
        await message.answer("Неверный формат. Введите HH:MM (например 21:30).")
        return
    user = await get_user_by_telegram_id(session, message.from_user.id)
    if not user:
        await state.clear()
        await message.answer("Сначала отправь /start и выбери часовой пояс.")
        return
    await update_notify_times(session, user.id, notify_evening_time=t)
    await state.clear()
    await message.answer(f"Вечернее время обновлено: {t.strftime('%H:%M')}", reply_markup=settings_submenu_keyboard())


@router.message(SettingsStates.awaiting_interval_minutes, F.text)
async def receive_interval_minutes(message: Message, session: AsyncSession, state: FSMContext):
    value = (message.text or "").strip()
    if not value.isdigit():
        await message.answer("Введите число (минуты), например 45.")
        return
    minutes = int(value)
    if not (5 <= minutes <= 720):
        await message.answer("Интервал должен быть в диапазоне 5-720 минут.")
        return
    user = await get_user_by_telegram_id(session, message.from_user.id)
    if not user:
        await state.clear()
        await message.answer("Сначала отправь /start и выбери часовой пояс.")
        return
    await update_morning_reminder_settings(session, user.id, interval_minutes=minutes)
    await state.clear()
    await message.answer(f"Интервал повторных напоминаний: {minutes} мин.", reply_markup=settings_submenu_keyboard())


@router.message(SettingsStates.awaiting_max_attempts, F.text)
async def receive_max_attempts(message: Message, session: AsyncSession, state: FSMContext):
    value = (message.text or "").strip()
    if not value.isdigit():
        await message.answer("Введите число (0-10), например 2.")
        return
    attempts = int(value)
    if not (0 <= attempts <= 10):
        await message.answer("Количество повторов должно быть в диапазоне 0-10.")
        return
    user = await get_user_by_telegram_id(session, message.from_user.id)
    if not user:
        await state.clear()
        await message.answer("Сначала отправь /start и выбери часовой пояс.")
        return
    await update_morning_reminder_settings(session, user.id, max_attempts=attempts)
    await state.clear()
    await message.answer(f"Максимум повторных утренних напоминаний: {attempts}.", reply_markup=settings_submenu_keyboard())

