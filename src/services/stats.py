"""Stats: /today, /history YYYY-MM, /stats (percentage, streaks)."""
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import Plan, Task, TaskStatus


async def get_today_plan(session: AsyncSession, user_id: int) -> Plan | None:
    today = date.today()
    r = await session.execute(
        select(Plan)
        .where(Plan.user_id == user_id, Plan.date == today)
        .options(selectinload(Plan.tasks).selectinload(Task.status))
    )
    return r.scalar_one_or_none()


async def get_plan_for_date(session: AsyncSession, user_id: int, d: date) -> Plan | None:
    r = await session.execute(
        select(Plan)
        .where(Plan.user_id == user_id, Plan.date == d)
        .options(selectinload(Plan.tasks).selectinload(Task.status))
    )
    return r.scalar_one_or_none()


async def get_history(
    session: AsyncSession,
    user_id: int,
    year: int,
    month: int,
) -> list[tuple[Plan, int, int]]:
    """
    Returns list of (plan, done_count, total) for the month.
    """
    from calendar import monthrange
    first = date(year, month, 1)
    last_day = monthrange(year, month)[1]
    last = date(year, month, last_day)
    r = await session.execute(
        select(Plan)
        .where(Plan.user_id == user_id, Plan.date >= first, Plan.date <= last)
        .options(selectinload(Plan.tasks).selectinload(Task.status))
        .order_by(Plan.date.desc())
    )
    plans = list(r.scalars().all())
    result = []
    for plan in plans:
        total = len(plan.tasks)
        done = sum(
            1 if (ts := t.status) and ts.status_enum == "done" else (0.5 if ts and ts.status_enum == "partial" else 0)
            for t in plan.tasks
        )
        result.append((plan, int(done), total))
    return result


async def get_completion_percent_for_plan(session: AsyncSession, plan: Plan) -> int:
    total = len(plan.tasks)
    if total == 0:
        return 0
    done = sum(
        1 if (ts := t.status) and ts.status_enum == "done" else (0.5 if ts and ts.status_enum == "partial" else 0)
        for t in plan.tasks
    )
    return int(round(100 * done / total))


async def get_stats(
    session: AsyncSession,
    user_id: int,
) -> dict[str, Any]:
    """
    Aggregate stats: total plans, completion percent over time, current streak (consecutive days with 100%).
    """
    r = await session.execute(
        select(Plan)
        .where(Plan.user_id == user_id)
        .options(selectinload(Plan.tasks).selectinload(Task.status))
        .order_by(Plan.date.desc())
    )
    plans = list(r.scalars().all())
    if not plans:
        return {"total_plans": 0, "avg_percent": 0, "current_streak": 0}

    total_plans = len(plans)
    percents = []
    for plan in plans:
        pct = await get_completion_percent_for_plan(session, plan)
        percents.append(pct)
    avg_percent = int(round(sum(percents) / len(percents))) if percents else 0

    # Current streak: consecutive days (from today backwards) with 100% completion
    today = date.today()
    streak = 0
    d = today
    plan_by_date = {p.date: p for p in plans}
    while True:
        plan = plan_by_date.get(d)
        if not plan or not plan.tasks:
            break
        pct = await get_completion_percent_for_plan(session, plan)
        if pct < 100:
            break
        streak += 1
        d -= timedelta(days=1)
    return {
        "total_plans": total_plans,
        "avg_percent": avg_percent,
        "current_streak": streak,
    }
