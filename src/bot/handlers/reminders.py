import re
from datetime import time
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.states import ReminderStates
from src.bot.user_flow import get_user_or_ask_timezone
from src.services.reminders import (
    add_custom_reminder,
    list_custom_reminders,
    toggle_custom_reminder,
    delete_custom_reminder,
    mark_reminder_done_today,
)
from src.bot.keyboards import custom_reminder_inline_keyboard, custom_reminder_off_keyboard

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

@router.message(Command("reminders"))
async def cmd_reminders(message: Message, session: AsyncSession):
    user = await get_user_or_ask_timezone(session, message.from_user.id, message)
    if not user:
        return
        
    reminders = await list_custom_reminders(session, user.id)
    if not reminders:
        await message.answer("У вас нет кастомных напоминаний. Добавьте: /reminder_add")
        return
        
    await message.answer("Ваши напоминания:")
    for r in reminders:
        text = f"⏰ {r.time_of_day.strftime('%H:%M')} | {r.description}\n"
        text += f"Повтор: каждые {r.repeat_interval_minutes} мин, до {r.max_attempts_per_day} раз"
        if not r.enabled:
            text += "\n(Отключено 🔕)"
            kb = custom_reminder_off_keyboard(r.id)
        else:
            kb = custom_reminder_inline_keyboard(r.id)
            
        await message.answer(text, reply_markup=kb)

@router.message(Command("reminder_add"))
async def cmd_reminder_add(message: Message, session: AsyncSession, state: FSMContext):
    user = await get_user_or_ask_timezone(session, message.from_user.id, message)
    if not user:
        return
        
    await state.set_state(ReminderStates.awaiting_time)
    await message.answer("Во сколько напоминать каждый день? (в формате HH:MM, например 14:30)")

@router.message(ReminderStates.awaiting_time, F.text, ~F.text.startswith("/"))
async def process_reminder_time(message: Message, state: FSMContext):
    t = _parse_hhmm((message.text or "").strip())
    if not t:
        await message.answer("Неверный формат. Введите HH:MM (например 14:30).")
        return
        
    await state.update_data(reminder_time=t.strftime('%H:%M'))
    await state.set_state(ReminderStates.awaiting_description)
    await message.answer("Введите текст напоминания (например: Выпить таблетку):")

@router.message(ReminderStates.awaiting_description, F.text, ~F.text.startswith("/"))
async def process_reminder_description(message: Message, state: FSMContext):
    desc = (message.text or "").strip()
    if not desc:
        await message.answer("Текст не может быть пустым. Введите текст напоминания:")
        return
        
    await state.update_data(reminder_desc=desc)
    await state.set_state(ReminderStates.awaiting_interval)
    await message.answer("Через сколько минут повторять напоминание, если не нажато «Выполнено»? (например, 30)")

@router.message(ReminderStates.awaiting_interval, F.text, ~F.text.startswith("/"))
async def process_reminder_interval(message: Message, state: FSMContext):
    val = (message.text or "").strip()
    if not val.isdigit() or not (1 <= int(val) <= 1440):
        await message.answer("Введите число минут от 1 до 1440.")
        return
        
    await state.update_data(reminder_interval=int(val))
    await state.set_state(ReminderStates.awaiting_max_attempts)
    await message.answer("Сколько раз максимум отправлять напоминание за день? (например, 3)")

@router.message(ReminderStates.awaiting_max_attempts, F.text, ~F.text.startswith("/"))
async def process_reminder_max_attempts(message: Message, session: AsyncSession, state: FSMContext):
    val = (message.text or "").strip()
    if not val.isdigit() or not (1 <= int(val) <= 50):
        await message.answer("Введите число попыток от 1 до 50.")
        return
        
    user = await get_user_or_ask_timezone(session, message.from_user.id, message)
    if not user:
        await state.clear()
        return
        
    data = await state.get_data()
    t = _parse_hhmm(data["reminder_time"])
    
    await add_custom_reminder(
        session=session,
        user_id=user.id,
        time_of_day=t,
        description=data["reminder_desc"],
        repeat_interval_minutes=data["reminder_interval"],
        max_attempts_per_day=int(val)
    )
    
    await state.clear()
    await message.answer(f"Напоминание сохранено! Оно сработает в {data['reminder_time']}.")

@router.callback_query(F.data.startswith("crem_done_"))
async def callback_crem_done(callback: CallbackQuery, session: AsyncSession):
    rem_id = int(callback.data.split("_")[-1])
    user = await get_user_or_ask_timezone(session, callback.from_user.id, callback.message)
    if not user:
        await callback.answer("Ошибка пользователя")
        return
        
    success = await mark_reminder_done_today(session, rem_id, user.id)
    if success:
        await session.commit()
        await callback.answer("Отмечено как выполненное на сегодня ✅")
        # Edit message to show it's done
        await callback.message.edit_text(callback.message.text + "\n\n✅ Выполнено!")
    else:
        await callback.answer("Напоминание не найдено или нет прав")

@router.callback_query(F.data.startswith("crem_off_"))
async def callback_crem_off(callback: CallbackQuery, session: AsyncSession):
    rem_id = int(callback.data.split("_")[-1])
    user = await get_user_or_ask_timezone(session, callback.from_user.id, callback.message)
    if not user:
        return
        
    success = await toggle_custom_reminder(session, rem_id, user.id, False)
    if success:
        await session.commit()
        await callback.answer("Напоминание отключено 🔕")
        await callback.message.edit_reply_markup(reply_markup=custom_reminder_off_keyboard(rem_id))
    else:
        await callback.answer("Напоминание не найдено")

@router.callback_query(F.data.startswith("crem_on_"))
async def callback_crem_on(callback: CallbackQuery, session: AsyncSession):
    rem_id = int(callback.data.split("_")[-1])
    user = await get_user_or_ask_timezone(session, callback.from_user.id, callback.message)
    if not user:
        return
        
    success = await toggle_custom_reminder(session, rem_id, user.id, True)
    if success:
        await session.commit()
        await callback.answer("Напоминание включено 🔔")
        await callback.message.edit_reply_markup(reply_markup=custom_reminder_inline_keyboard(rem_id))
    else:
        await callback.answer("Напоминание не найдено")

@router.callback_query(F.data.startswith("crem_del_"))
async def callback_crem_del(callback: CallbackQuery, session: AsyncSession):
    rem_id = int(callback.data.split("_")[-1])
    user = await get_user_or_ask_timezone(session, callback.from_user.id, callback.message)
    if not user:
        return
        
    success = await delete_custom_reminder(session, rem_id, user.id)
    if success:
        await session.commit()
        await callback.answer("Напоминание удалено 🗑")
        await callback.message.edit_text("🗑 Напоминание удалено.")
    else:
        await callback.answer("Напоминание не найдено")