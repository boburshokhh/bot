"""Evening review: task statuses and comments."""
from datetime import date

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards import evening_done_keyboard, evening_inline_keyboard
from src.bot.states import PlanStates
from src.bot.text import format_evening_plan, EVENING_AFTER_STATUSES, EVENING_DAY_COMMENT_PROMPT
from src.services.evening import (
    set_task_status,
    get_completion_for_plan,
    update_task_comment,
    DONE,
    PARTIAL,
    FAILED,
)
from src.services.plan import get_plan_by_id

router = Router()


def _task_status_from_callback(callback_data: str) -> str | None:
    if callback_data.startswith("task_done_"):
        return DONE
    if callback_data.startswith("task_partial_"):
        return PARTIAL
    if callback_data.startswith("task_failed_"):
        return FAILED
    return None


def _task_id_from_callback(callback_data: str) -> int | None:
    try:
        return int(callback_data.split("_")[-1])
    except (IndexError, ValueError):
        return None


@router.callback_query(F.data.startswith("task_done_"), PlanStates.awaiting_confirmation)
@router.callback_query(F.data.startswith("task_partial_"), PlanStates.awaiting_confirmation)
@router.callback_query(F.data.startswith("task_failed_"), PlanStates.awaiting_confirmation)
async def set_status_callback(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    status = _task_status_from_callback(callback.data or "")
    task_id = _task_id_from_callback(callback.data or "")
    if not status or task_id is None:
        await callback.answer("Ошибка")
        return
    await set_task_status(session, task_id, status, comment=None)
    await callback.answer("Сохранено")
    data = await state.get_data()
    plan_id = data.get("plan_id")
    plan_date = data.get("plan_date") or date.today()
    if isinstance(plan_date, str):
        from datetime import datetime as dt
        plan_date = dt.strptime(plan_date, "%Y-%m-%d").date()
    if not plan_id:
        return
    plan = await get_plan_by_id(session, plan_id)
    if not plan:
        return
    tasks_with_status = [
        (t.text, t.status.status_enum if t.status else None)
        for t in sorted(plan.tasks, key=lambda x: x.position)
    ]
    done, total, percent = await get_completion_for_plan(session, plan.id)
    text = format_evening_plan(plan_date, tasks_with_status)
    all_responded = all(t.status for t in plan.tasks)
    if all_responded and total > 0:
        text += "\n\n" + EVENING_DAY_COMMENT_PROMPT.format(done=int(done), total=total, percent=percent)
        await callback.message.edit_text(text, reply_markup=evening_done_keyboard())
    else:
        await callback.message.edit_text(text, reply_markup=evening_inline_keyboard([t.id for t in plan.tasks]))


@router.callback_query(F.data.startswith("task_comment_"), PlanStates.awaiting_confirmation)
async def ask_comment_callback(callback: CallbackQuery, state: FSMContext):
    task_id = _task_id_from_callback(callback.data or "")
    if task_id is None:
        await callback.answer("Ошибка")
        return
    await state.update_data(comment_task_id=task_id)
    await state.set_state(PlanStates.awaiting_comment)
    await callback.answer()
    await callback.message.answer("Напиши комментарий к этой задаче (или отправь «-» чтобы пропустить):")


@router.message(PlanStates.awaiting_comment, F.text)
async def receive_comment(message: Message, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    task_id = data.get("comment_task_id")
    if task_id is None:
        await state.clear()
        return
    comment = None if (message.text or "").strip() in ("-", "") else (message.text or "").strip()[:500]
    await update_task_comment(session, task_id, comment)
    await state.set_state(PlanStates.awaiting_confirmation)
    await state.update_data(comment_task_id=None)
    plan_id = data.get("plan_id")
    plan_date = data.get("plan_date") or date.today()
    if isinstance(plan_date, str):
        from datetime import datetime as dt
        plan_date = dt.strptime(plan_date, "%Y-%m-%d").date()
    plan = await get_plan_by_id(session, plan_id) if plan_id else None
    if plan:
        tasks_with_status = [
            (t.text, t.status.status_enum if t.status else None)
            for t in sorted(plan.tasks, key=lambda x: x.position)
        ]
        text = format_evening_plan(plan_date, tasks_with_status) + EVENING_AFTER_STATUSES
        await message.answer(text, reply_markup=evening_inline_keyboard([t.id for t in plan.tasks]))
    else:
        await message.answer("План не найден.")
        await state.clear()


@router.callback_query(F.data == "day_comment", PlanStates.awaiting_confirmation)
async def day_comment_btn(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("Напиши комментарий к дню (или «-» чтобы пропустить):")
    await state.update_data(awaiting_day_comment=True)


@router.message(PlanStates.awaiting_confirmation, F.text)
async def receive_day_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    if not data.get("awaiting_day_comment"):
        return
    await state.update_data(awaiting_day_comment=False)
    await state.clear()
    if (message.text or "").strip() and (message.text or "").strip() != "-":
        await message.answer("Комментарий к дню сохранён. Итоги дня сохранены. До завтра!")
    else:
        await message.answer("Итоги дня сохранены. До завтра!")


@router.callback_query(F.data == "day_done", PlanStates.awaiting_confirmation)
async def day_done_btn(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("Готово!")
    await callback.message.answer("Итоги дня сохранены. До завтра!")