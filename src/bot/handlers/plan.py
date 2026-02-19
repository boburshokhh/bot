"""Plan submission (morning flow)."""
from datetime import date

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards import morning_reply_keyboard
from src.bot.states import PlanStates
from src.bot.text import (
    MORNING_PROMPT,
    PLAN_ALREADY_EXISTS_TODAY,
    PLAN_DELETED,
    PLAN_NOT_FOUND,
    PLAN_OPENED_MANUALLY,
    PLAN_SAVED,
    PLAN_SKIPPED,
)
from src.bot.user_flow import get_user_or_ask_timezone
from src.logic.plan_parser import parse_plan_lines, validate_plan_text
from src.services.plan import delete_plan, get_plan_for_date, save_plan

router = Router()


@router.message(Command("plan"))
async def cmd_plan(message: Message, session: AsyncSession, state: FSMContext):
    user = await get_user_or_ask_timezone(session, message.from_user.id, message)
    if not user:
        return
    today = date.today()
    existing_plan = await get_plan_for_date(session, user.id, today)
    if existing_plan:
        await message.answer(PLAN_ALREADY_EXISTS_TODAY)
        return

    await state.set_state(PlanStates.awaiting_plan)
    await state.update_data(plan_date=today.isoformat())
    await message.answer(f"{PLAN_OPENED_MANUALLY}\n\n{MORNING_PROMPT}", reply_markup=morning_reply_keyboard())


@router.message(PlanStates.awaiting_plan, F.text, ~F.text.in_({"Отправил ✅", "Пропустить сегодня ⏭"}))
async def receive_plan(message: Message, session: AsyncSession, state: FSMContext):

    ok, err = validate_plan_text(message.text or "")
    if not ok:
        await message.answer(err)
        return
    user = await get_user_or_ask_timezone(session, message.from_user.id, message)
    if not user:
        return
    data = await state.get_data()
    plan_date = data.get("plan_date")
    if plan_date and isinstance(plan_date, str):
        from datetime import datetime
        plan_date = datetime.strptime(plan_date, "%Y-%m-%d").date()
    if not plan_date:
        plan_date = date.today()
    task_texts = parse_plan_lines(message.text)
    await save_plan(session, user.id, plan_date, task_texts)
    await state.clear()
    await message.answer(PLAN_SAVED)


@router.message(PlanStates.awaiting_plan, F.text == "Пропустить сегодня ⏭")
async def skip_plan(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(PLAN_SKIPPED)


@router.message(PlanStates.awaiting_plan, F.text == "Отправил ✅")
async def already_sent(message: Message):
    await message.answer("Пришли план текстом — каждый пункт с новой строки.")


@router.message(Command("delete_plan"))
async def cmd_delete_plan(message: Message, session: AsyncSession):
    user = await get_user_or_ask_timezone(session, message.from_user.id, message)
    if not user:
        return
    today = date.today()
    deleted = await delete_plan(session, user.id, today)
    if deleted:
        await message.answer(PLAN_DELETED)
    else:
        await message.answer(PLAN_NOT_FOUND)