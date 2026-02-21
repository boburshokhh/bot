"""Logic for custom daily reminders scheduling and CRUD."""
import logging
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import CustomReminder, User

logger = logging.getLogger(__name__)


def compute_next_fire_utc(user_tz: str, time_of_day: time, base_utc: datetime, day_of_month: int | None = None) -> tuple[datetime, date]:
    """
    Given a user's timezone, their desired time of day, and a base UTC time (usually now),
    calculate the next UTC datetime when the reminder should fire.
    If day_of_month is provided, it schedules for that day of the month (clamping to the last day if needed).
    Also returns the local date corresponding to that fire time.
    """
    import calendar
    try:
        tz = ZoneInfo(user_tz)
    except Exception as e:
        logger.warning(f"Invalid timezone {user_tz}: {e}. Falling back to UTC.")
        tz = ZoneInfo("UTC")
        
    local_base = base_utc.astimezone(tz)
    
    if day_of_month is None:
        target_local = local_base.replace(
            hour=time_of_day.hour,
            minute=time_of_day.minute,
            second=0,
            microsecond=0
        )
        if target_local <= local_base:
            target_local += timedelta(days=1)
        return target_local.astimezone(timezone.utc).replace(tzinfo=None), target_local.date()
    else:
        year = local_base.year
        month = local_base.month
        _, last_day = calendar.monthrange(year, month)
        target_day = min(day_of_month, last_day)
        
        target_local = local_base.replace(
            day=target_day,
            hour=time_of_day.hour,
            minute=time_of_day.minute,
            second=0,
            microsecond=0
        )
        
        if target_local <= local_base:
            month += 1
            if month > 12:
                month = 1
                year += 1
            _, last_day = calendar.monthrange(year, month)
            target_day = min(day_of_month, last_day)
            target_local = local_base.replace(
                year=year,
                month=month,
                day=target_day,
                hour=time_of_day.hour,
                minute=time_of_day.minute,
                second=0,
                microsecond=0
            )
            
        return target_local.astimezone(timezone.utc).replace(tzinfo=None), target_local.date()


async def add_custom_reminder(
    session: AsyncSession,
    user_id: int,
    time_of_day: time,
    description: str,
    repeat_interval_minutes: int,
    max_attempts_per_day: int,
    day_of_month: int | None = None
) -> CustomReminder:
    """Add a new custom reminder and initialize its schedule."""
    r = await session.execute(select(User.timezone).where(User.id == user_id))
    user_tz = r.scalar_one_or_none() or "UTC"
    
    now_utc = datetime.now(timezone.utc)
    next_fire_utc, cycle_date = compute_next_fire_utc(user_tz, time_of_day, now_utc, day_of_month)
    
    reminder = CustomReminder(
        user_id=user_id,
        time_of_day=time_of_day,
        description=description,
        repeat_interval_minutes=repeat_interval_minutes,
        max_attempts_per_day=max_attempts_per_day,
        day_of_month=day_of_month,
        cycle_local_date=cycle_date,
        attempts_sent_today=0,
        done_today=False,
        next_fire_at_utc=next_fire_utc,
        enabled=True
    )
    session.add(reminder)
    await session.flush()
    return reminder


async def list_custom_reminders(session: AsyncSession, user_id: int) -> list[CustomReminder]:
    r = await session.execute(
        select(CustomReminder)
        .where(CustomReminder.user_id == user_id)
        .order_by(CustomReminder.time_of_day)
    )
    return list(r.scalars().all())


async def get_reminder_stats(session: AsyncSession, user_id: int) -> dict:
    """Агрегированная статистика по напоминаниям пользователя."""
    q = select(CustomReminder).where(CustomReminder.user_id == user_id)
    r_total = await session.execute(select(func.count()).select_from(q.subquery()))
    total = r_total.scalar() or 0

    r_enabled = await session.execute(
        select(func.count())
        .select_from(CustomReminder)
        .where(CustomReminder.user_id == user_id, CustomReminder.enabled == True)
    )
    enabled = r_enabled.scalar() or 0

    r_done = await session.execute(
        select(func.count())
        .select_from(CustomReminder)
        .where(CustomReminder.user_id == user_id, CustomReminder.done_today == True)
    )
    done_today = r_done.scalar() or 0

    r_sent = await session.execute(
        select(func.coalesce(func.sum(CustomReminder.attempts_sent_today), 0)).where(
            CustomReminder.user_id == user_id
        )
    )
    sent_today = int(r_sent.scalar() or 0)

    return {
        "total": total,
        "enabled": enabled,
        "disabled": total - enabled,
        "done_today": done_today,
        "sent_today": sent_today,
    }


async def get_custom_reminder(session: AsyncSession, reminder_id: int) -> CustomReminder | None:
    r = await session.execute(
        select(CustomReminder).where(CustomReminder.id == reminder_id).options(selectinload(CustomReminder.user))
    )
    return r.scalar_one_or_none()


async def delete_custom_reminder(session: AsyncSession, reminder_id: int, user_id: int) -> bool:
    r = await session.execute(
        delete(CustomReminder).where(
            CustomReminder.id == reminder_id, 
            CustomReminder.user_id == user_id
        )
    )
    return r.rowcount > 0


async def update_custom_reminder(
    session: AsyncSession,
    reminder_id: int,
    user_id: int,
    **kwargs
) -> bool:
    """Обновить поля напоминания. При смене времени или дня пересчитывается next_fire_at_utc."""
    reminder = await get_custom_reminder(session, reminder_id)
    if not reminder or reminder.user_id != user_id:
        return False
        
    time_of_day = kwargs.get("time_of_day")
    description = kwargs.get("description")
    repeat_interval_minutes = kwargs.get("repeat_interval_minutes")
    max_attempts_per_day = kwargs.get("max_attempts_per_day")
    day_of_month = kwargs.get("day_of_month", -1)
    
    if time_of_day is not None:
        reminder.time_of_day = time_of_day
    if description is not None:
        reminder.description = description.strip()[:500] or reminder.description
    if repeat_interval_minutes is not None:
        reminder.repeat_interval_minutes = repeat_interval_minutes
    if max_attempts_per_day is not None:
        reminder.max_attempts_per_day = max_attempts_per_day
    if day_of_month != -1:
        reminder.day_of_month = day_of_month

    if time_of_day is not None or day_of_month != -1:
        if reminder.user:
            now_utc = datetime.now(timezone.utc)
            next_fire_utc, cycle_date = compute_next_fire_utc(
                reminder.user.timezone, reminder.time_of_day, now_utc, reminder.day_of_month
            )
            reminder.next_fire_at_utc = next_fire_utc
            reminder.cycle_local_date = cycle_date
    return True


async def toggle_custom_reminder(session: AsyncSession, reminder_id: int, user_id: int, enabled: bool) -> bool:
    r = await session.execute(
        update(CustomReminder)
        .where(CustomReminder.id == reminder_id, CustomReminder.user_id == user_id)
        .values(enabled=enabled)
    )
    if r.rowcount > 0 and enabled:
        # Reschedule it to make sure next_fire_at_utc is valid and in the future
        reminder = await get_custom_reminder(session, reminder_id)
        if reminder and reminder.user:
            now_utc = datetime.now(timezone.utc)
            next_fire_utc, cycle_date = compute_next_fire_utc(
                reminder.user.timezone, reminder.time_of_day, now_utc, reminder.day_of_month
            )
            reminder.next_fire_at_utc = next_fire_utc
            reminder.cycle_local_date = cycle_date
            reminder.attempts_sent_today = 0
            reminder.done_today = False
    return r.rowcount > 0


async def mark_reminder_done_today(session: AsyncSession, reminder_id: int, user_id: int) -> bool:
    reminder = await get_custom_reminder(session, reminder_id)
    if not reminder or reminder.user_id != user_id:
        return False
        
    now_utc = datetime.now(timezone.utc)
    next_fire_utc, cycle_date = compute_next_fire_utc(
        reminder.user.timezone, reminder.time_of_day, now_utc, reminder.day_of_month
    )
    
    reminder.done_today = True
    reminder.next_fire_at_utc = next_fire_utc
    reminder.cycle_local_date = cycle_date
    reminder.attempts_sent_today = 0
    reminder.locked_until_utc = None
    
    return True
