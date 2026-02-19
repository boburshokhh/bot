"""Plan submission (morning flow)."""
from datetime import date

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.states import PlanStates
from src.bot.text import PLAN_SAVED, PLAN_SKIPPED
from src.logic.plan_parser import parse_plan_lines, validate_plan_text
from src.services.plan import save_plan
from src.services.user import get_user_by_telegram_id

router = Router()


@router.message(PlanStates.awaiting_plan, F.text, ~F.text.in_({"Отправил ✅", "Пропустить сегодня ⏭"}))
async def receive_plan(message: Message, session: AsyncSession, state: FSMContext):

    ok, err = validate_plan_text(message.text or "")
    if not ok:
        await message.answer(err)
        return
    user = await get_user_by_telegram_id(session, message.from_user.id)
    if not user:
        await message.answer("Сначала отправь /start и выбери часовой пояс.")
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