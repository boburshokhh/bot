"""Stats: /today, /history, /stats."""
from datetime import date
import re

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.user_flow import get_user_or_run_onboarding
from src.services.stats import get_today_plan, get_history, get_stats, get_completion_percent_for_plan

router = Router()


@router.message(Command("today"))
async def cmd_today(message: Message, session: AsyncSession, state: FSMContext):
    user = await get_user_or_run_onboarding(session, message.from_user.id, message, state)
    if not user:
        return
    plan = await get_today_plan(session, user.id)
    if not plan or not plan.tasks:
        await message.answer("На сегодня плана нет.")
        return
    pct = await get_completion_percent_for_plan(session, plan)
    lines = [f"План на {plan.date}:", ""]
    for t in sorted(plan.tasks, key=lambda x: x.position):
        st = t.status
        icon = "✅" if st and st.status_enum == "done" else ("⚠" if st and st.status_enum == "partial" else "❌")
        lines.append(f"• {t.text} {icon}")
    lines.append(f"\nВыполнено: {pct}%")
    await message.answer("\n".join(lines))


@router.message(Command("history"), F.text.regexp(re.compile(r"^/history\s+(\d{4})-(\d{2})$")))
async def cmd_history(message: Message, session: AsyncSession, state: FSMContext):
    user = await get_user_or_run_onboarding(session, message.from_user.id, message, state)
    if not user:
        return
    match = re.match(r"^/history\s+(\d{4})-(\d{2})$", message.text or "")
    if not match:
        await message.answer("Использование: /history YYYY-MM (например /history 2025-01)")
        return
    year, month = int(match.group(1)), int(match.group(2))
    if not (1 <= month <= 12):
        await message.answer("Месяц должен быть от 01 до 12.")
        return
    items = await get_history(session, user.id, year, month)
    if not items:
        await message.answer(f"За {year}-{month:02d} планов нет.")
        return
    lines = [f"История за {year}-{month:02d}:", ""]
    for plan, done, total in items:
        pct = int(round(100 * done / total)) if total else 0
        lines.append(f"{plan.date}: {done}/{total} ({pct}%)")
    await message.answer("\n".join(lines))


@router.message(Command("history"))
async def cmd_history_usage(message: Message):
    await message.answer("Использование: /history YYYY-MM (например /history 2025-01)")


@router.message(Command("stats"))
async def cmd_stats(message: Message, session: AsyncSession, state: FSMContext):
    user = await get_user_or_run_onboarding(session, message.from_user.id, message, state)
    if not user:
        return
    s = await get_stats(session, user.id)
    await message.answer(
        f"Всего планов: {s['total_plans']}\n"
        f"Средний % выполнения: {s['avg_percent']}%\n"
        f"Текущий стрик (дней подряд 100%): {s['current_streak']}"
    )
