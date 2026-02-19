"""WebApp API: today, tasks, settings, history, stats."""
from __future__ import annotations

from datetime import date, datetime, time
import re
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.auth import get_webapp_user
from src.db.models import Plan, Task, User
from src.db.session import get_async_session
from src.services.evening import DONE, FAILED, PARTIAL, set_task_status, update_task_comment
from src.services.plan import save_plan
from src.services.stats import get_history, get_stats, get_today_plan
from src.services.user import (
    update_morning_reminder_settings,
    update_notify_times,
    update_user_timezone,
)

router = APIRouter(prefix="/api", tags=["webapp"])
VALID_STATUSES = {DONE, PARTIAL, FAILED}


class TaskStatusUpdatePayload(BaseModel):
    status: str | None = None
    comment: str | None = None


class SettingsUpdatePayload(BaseModel):
    timezone: str | None = None
    morning_time: str | None = None
    evening_time: str | None = None
    reminder_interval_minutes: int | None = Field(default=None, ge=5, le=720)
    reminder_max_attempts: int | None = Field(default=None, ge=0, le=10)


class CreateTodayPlanPayload(BaseModel):
    tasks: list[str]


def _parse_hhmm(value: str) -> time:
    if not re.fullmatch(r"\d{2}:\d{2}", value):
        raise HTTPException(status_code=400, detail="Time format must be HH:MM")
    hour, minute = value.split(":")
    h = int(hour)
    m = int(minute)
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise HTTPException(status_code=400, detail="Time is out of range")
    return time(h, m)


def _serialize_today(plan: Plan | None) -> dict:
    if not plan or not plan.tasks:
        return {"date": date.today().isoformat(), "tasks": [], "exists": False}
    tasks = []
    for task in sorted(plan.tasks, key=lambda x: x.position):
        tasks.append(
            {
                "id": task.id,
                "position": task.position,
                "text": task.text,
                "status": task.status.status_enum if task.status else None,
                "comment": task.status.comment if task.status else None,
            }
        )
    return {"date": plan.date.isoformat(), "tasks": tasks, "exists": True, "plan_id": plan.id}


@router.get("/today")
async def api_today(
    user: User = Depends(get_webapp_user),
    session: AsyncSession = Depends(get_async_session),
):
    plan = await get_today_plan(session, user.id)
    return _serialize_today(plan)


@router.post("/plan/today")
async def api_create_today_plan(
    payload: CreateTodayPlanPayload,
    user: User = Depends(get_webapp_user),
    session: AsyncSession = Depends(get_async_session),
):
    cleaned = [x.strip()[:500] for x in payload.tasks if x and x.strip()]
    if not cleaned:
        raise HTTPException(status_code=400, detail="At least one task is required")
    plan = await save_plan(session, user.id, date.today(), cleaned)
    return {"ok": True, "plan_id": plan.id, "task_count": len(cleaned)}


@router.put("/tasks/{task_id}/status")
async def api_set_task_status(
    task_id: int,
    payload: TaskStatusUpdatePayload,
    user: User = Depends(get_webapp_user),
    session: AsyncSession = Depends(get_async_session),
):
    r = await session.execute(
        select(Task)
        .join(Plan, Plan.id == Task.plan_id)
        .where(Task.id == task_id, Plan.user_id == user.id)
        .options(selectinload(Task.status))
    )
    task = r.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if payload.status is not None:
        if payload.status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status")
        await set_task_status(
            session,
            task_id=task.id,
            status_enum=payload.status,
            comment=(payload.comment or "")[:500] if payload.comment is not None else None,
        )
    elif payload.comment is not None:
        await update_task_comment(session, task_id=task.id, comment=(payload.comment or "")[:500] or None)
    else:
        raise HTTPException(status_code=400, detail="Provide status or comment")

    return {"ok": True}


@router.get("/settings")
async def api_get_settings(user: User = Depends(get_webapp_user)):
    return {
        "timezone": user.timezone,
        "morning_time": user.notify_morning_time.strftime("%H:%M"),
        "evening_time": user.notify_evening_time.strftime("%H:%M"),
        "reminder_interval_minutes": user.morning_reminder_interval_minutes,
        "reminder_max_attempts": user.morning_reminder_max_attempts,
    }


@router.put("/settings")
async def api_update_settings(
    payload: SettingsUpdatePayload,
    user: User = Depends(get_webapp_user),
    session: AsyncSession = Depends(get_async_session),
):
    if payload.timezone is not None:
        try:
            ZoneInfo(payload.timezone)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid timezone") from exc
        await update_user_timezone(session, user.id, payload.timezone)
    if payload.morning_time is not None:
        await update_notify_times(session, user.id, notify_morning_time=_parse_hhmm(payload.morning_time))
    if payload.evening_time is not None:
        await update_notify_times(session, user.id, notify_evening_time=_parse_hhmm(payload.evening_time))
    if payload.reminder_interval_minutes is not None or payload.reminder_max_attempts is not None:
        await update_morning_reminder_settings(
            session,
            user.id,
            interval_minutes=payload.reminder_interval_minutes,
            max_attempts=payload.reminder_max_attempts,
        )
    return {"ok": True}


@router.get("/stats")
async def api_stats(
    user: User = Depends(get_webapp_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await get_stats(session, user.id)


@router.get("/history")
async def api_history(
    month: str = Query(default_factory=lambda: datetime.now().strftime("%Y-%m")),
    user: User = Depends(get_webapp_user),
    session: AsyncSession = Depends(get_async_session),
):
    if not re.fullmatch(r"\d{4}-\d{2}", month):
        raise HTTPException(status_code=400, detail="Month must be YYYY-MM")
    year, mm = month.split("-")
    year_int, month_int = int(year), int(mm)
    if not (1 <= month_int <= 12):
        raise HTTPException(status_code=400, detail="Month out of range")
    items = await get_history(session, user.id, year_int, month_int)
    data = []
    for plan, done, total in items:
        percent = int(round((100 * done / total))) if total else 0
        data.append(
            {
                "date": plan.date.isoformat(),
                "done": done,
                "total": total,
                "percent": percent,
            }
        )
    return {"month": month, "items": data}
