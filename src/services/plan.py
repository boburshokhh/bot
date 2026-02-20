"""Plan creation and update. Idempotent by (user_id, date)."""
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import Plan, Task, User
from src.logic.plan_parser import parse_plan_lines


async def save_plan(
    session: AsyncSession,
    user_id: int,
    plan_date: date,
    task_texts: list[str],
) -> Plan:
    """
    Save or update plan for user+date. Replaces existing tasks (idempotent).
    task_texts should already be validated (e.g. from parse_plan_lines).
    """
    r = await session.execute(
        select(Plan).where(Plan.user_id == user_id, Plan.date == plan_date)
    )
    plan = r.scalar_one_or_none()
    if plan:
        # Delete existing tasks and replace
        for t in plan.tasks:
            await session.delete(t)
        await session.flush()
    else:
        plan = Plan(user_id=user_id, date=plan_date)
        session.add(plan)
        await session.flush()
    for i, text in enumerate(task_texts):
        task = Task(plan_id=plan.id, position=i, text=text.strip()[:500])
        session.add(task)
    await session.flush()
    await session.refresh(plan, ["tasks"])
    return plan


async def get_plan_for_date(
    session: AsyncSession,
    user_id: int,
    plan_date: date,
) -> Plan | None:
    r = await session.execute(
        select(Plan)
        .where(Plan.user_id == user_id, Plan.date == plan_date)
        .options(selectinload(Plan.tasks).selectinload(Task.status))
    )
    return r.scalar_one_or_none()


async def get_plan_by_id(session: AsyncSession, plan_id: int) -> Plan | None:
    r = await session.execute(
        select(Plan)
        .where(Plan.id == plan_id)
        .options(selectinload(Plan.tasks).selectinload(Task.status))
    )
    return r.scalar_one_or_none()


async def get_task_with_plan(session: AsyncSession, task_id: int) -> Task | None:
    """Load task with plan (plan has id, date, user_id). For access check and plan context."""
    r = await session.execute(
        select(Task).where(Task.id == task_id).options(selectinload(Task.plan))
    )
    return r.scalar_one_or_none()


async def delete_plan(
    session: AsyncSession,
    user_id: int,
    plan_date: date,
) -> bool:
    """
    Delete plan for user+date. Returns True if plan was deleted, False if not found.
    Tasks and TaskStatus are deleted automatically via cascade.
    """
    r = await session.execute(
        select(Plan).where(Plan.user_id == user_id, Plan.date == plan_date)
    )
    plan = r.scalar_one_or_none()
    if not plan:
        return False
    await session.delete(plan)
    await session.flush()
    return True
