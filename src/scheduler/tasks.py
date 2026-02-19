"""Celery tasks: send morning/evening prompts with retry."""
import asyncio
import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

from aiogram import Bot
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import selectinload

from src.config import Settings
from src.db.models import User, Plan, Task, NotificationLog
from src.bot.text import MORNING_PROMPT, REMINDER_MORNING, REMINDER_EVENING
from src.bot.keyboards import morning_reply_keyboard, evening_inline_keyboard
from src.bot.text import format_evening_plan
from src.services.notifications import (
    log_notification,
    TYPE_MORNING,
    TYPE_EVENING,
    STATUS_SENT,
    STATUS_FAILED,
    STATUS_RETRIED,
)
from src.scheduler.celery_app import app
from src.scheduler.fsm_helper import set_awaiting_plan, set_awaiting_confirmation

logger = logging.getLogger(__name__)


def _get_async_session():
    settings = Settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return factory, engine


def compute_next_morning_reminder_countdown(
    *,
    interval_minutes: int,
    max_attempts: int,
    next_attempt: int,
) -> int | None:
    """Return countdown in seconds for next reminder attempt or None if no more attempts."""
    safe_interval = max(1, int(interval_minutes))
    safe_max_attempts = max(0, int(max_attempts))
    if next_attempt < 1 or next_attempt > safe_max_attempts:
        return None
    return safe_interval * 60


async def _get_morning_reminder_policy(user_id: int) -> tuple[int, int]:
    """Return per-user morning reminder policy: (interval_minutes, max_attempts)."""
    factory, engine = _get_async_session()
    try:
        async with factory() as session:
            r = await session.execute(select(User).where(User.id == user_id))
            user = r.scalar_one_or_none()
            if not user:
                return 60, 1
            interval_minutes = max(1, int(user.morning_reminder_interval_minutes or 60))
            max_attempts = max(0, int(user.morning_reminder_max_attempts or 1))
            return interval_minutes, max_attempts
    finally:
        await engine.dispose()


async def _send_morning(user_id: int, plan_date: date, attempt_count: int) -> None:
    settings = Settings()
    factory, engine = _get_async_session()
    async with factory() as session:
        r = await session.execute(select(User).where(User.id == user_id))
        user = r.scalar_one_or_none()
        if not user:
            logger.warning("User id=%s not found", user_id)
            await engine.dispose()
            return
        telegram_id = user.telegram_id
    await engine.dispose()

    text = REMINDER_MORNING if attempt_count > 0 else MORNING_PROMPT
    bot = Bot(token=settings.telegram_bot_token)
    try:
        await bot.send_message(
            telegram_id,
            text,
            reply_markup=morning_reply_keyboard(),
        )
        await set_awaiting_plan(settings.redis_url, settings.telegram_bot_token, telegram_id, plan_date)
        factory2, engine2 = _get_async_session()
        async with factory2() as session:
            await log_notification(
                session, user_id, TYPE_MORNING, STATUS_SENT, {"date": plan_date.isoformat(), "attempt": attempt_count}
            )
            await session.commit()
        await engine2.dispose()
    except Exception as e:
        logger.exception("Morning send failed user_id=%s: %s", user_id, e)
        factory2, engine2 = _get_async_session()
        async with factory2() as session:
            await log_notification(
                session, user_id, TYPE_MORNING, STATUS_RETRIED if attempt_count > 0 else STATUS_FAILED, {"error": str(e), "attempt": attempt_count}
            )
            await session.commit()
        await engine2.dispose()
        raise
    finally:
        await bot.session.close()


async def _send_evening(user_id: int, plan_date: date, attempt_count: int) -> None:
    settings = Settings()
    factory, engine = _get_async_session()
    text = None
    task_ids = []
    plan_id = None
    async with factory() as session:
        r = await session.execute(select(User).where(User.id == user_id))
        user = r.scalar_one_or_none()
        if not user:
            logger.warning("User id=%s not found", user_id)
            await engine.dispose()
            return
        telegram_id = user.telegram_id
        r = await session.execute(
            select(Plan)
            .where(Plan.user_id == user_id, Plan.date == plan_date)
            .options(selectinload(Plan.tasks).selectinload(Task.status))
        )
        plan = r.scalar_one_or_none()
        if not plan or not plan.tasks:
            await engine.dispose()
            bot = Bot(token=settings.telegram_bot_token)
            try:
                await bot.send_message(telegram_id, "План на сегодня не найден. Создай план утром.")
            finally:
                await bot.session.close()
            return
        tasks_with_status = [
            (t.text, t.status.status_enum if t.status else None)
            for t in sorted(plan.tasks, key=lambda x: x.position)
        ]
        text = format_evening_plan(plan_date, tasks_with_status)
        task_ids = [t.id for t in plan.tasks]
        plan_id = plan.id
        await set_awaiting_confirmation(
            settings.redis_url, settings.telegram_bot_token, telegram_id, plan_id, plan_date, user_id
        )
        await session.commit()
    await engine.dispose()

    bot = Bot(token=settings.telegram_bot_token)
    try:
        await bot.send_message(
            telegram_id,
            text,
            reply_markup=evening_inline_keyboard(task_ids),
        )
        factory2, engine2 = _get_async_session()
        async with factory2() as session:
            await log_notification(
                session, user_id, TYPE_EVENING, STATUS_SENT, {"plan_id": plan_id, "attempt": attempt_count}
            )
            await session.commit()
        await engine2.dispose()
    except Exception as e:
        logger.exception("Evening send failed user_id=%s: %s", user_id, e)
        factory2, engine2 = _get_async_session()
        async with factory2() as session:
            await log_notification(
                session, user_id, TYPE_EVENING, STATUS_RETRIED if attempt_count > 0 else STATUS_FAILED, {"error": str(e)}
            )
            await session.commit()
        await engine2.dispose()
        raise
    finally:
        await bot.session.close()


@app.task(bind=True, max_retries=3)
def send_morning_prompt(self, user_id: int, plan_date: str, attempt_count: int = 0):
    """Send morning plan request. plan_date is ISO (YYYY-MM-DD)."""
    d = date.fromisoformat(plan_date)
    try:
        asyncio.run(_send_morning(user_id, d, attempt_count))
        interval_minutes, max_attempts = asyncio.run(_get_morning_reminder_policy(user_id))
        countdown = compute_next_morning_reminder_countdown(
            interval_minutes=interval_minutes,
            max_attempts=max_attempts,
            next_attempt=1,
        )
        if countdown is not None:
            send_morning_reminder.apply_async(
                args=[user_id, plan_date, 1],
                countdown=countdown,
            )
    except Exception as exc:
        countdown = 2 ** (attempt_count + 1) * 60
        raise self.retry(exc=exc, countdown=countdown)


@app.task
def send_morning_reminder(user_id: int, plan_date: str, reminder_attempt: int = 1):
    """Reminder(s) after morning prompt if user hasn't submitted a plan yet."""
    async def _run():
        factory, engine = _get_async_session()
        d = date.fromisoformat(plan_date)
        should_send = False
        telegram_id = None
        interval_minutes = 60
        max_attempts = 1
        async with factory() as session:
            r = await session.execute(select(Plan).where(Plan.user_id == user_id, Plan.date == d))
            if r.scalar_one_or_none() is not None:
                await engine.dispose()
                return
            r = await session.execute(select(User).where(User.id == user_id))
            user = r.scalar_one_or_none()
            if not user:
                await engine.dispose()
                return
            interval_minutes = max(1, int(user.morning_reminder_interval_minutes or 60))
            max_attempts = max(0, int(user.morning_reminder_max_attempts or 1))
            if reminder_attempt > max_attempts:
                await engine.dispose()
                return
            should_send = True
            telegram_id = user.telegram_id
        await engine.dispose()
        if not should_send or telegram_id is None:
            return
        settings = Settings()
        bot = Bot(token=settings.telegram_bot_token)
        try:
            await bot.send_message(telegram_id, REMINDER_MORNING, reply_markup=morning_reply_keyboard())
        finally:
            await bot.session.close()

        countdown = compute_next_morning_reminder_countdown(
            interval_minutes=interval_minutes,
            max_attempts=max_attempts,
            next_attempt=reminder_attempt + 1,
        )
        if countdown is not None:
            send_morning_reminder.apply_async(
                args=[user_id, plan_date, reminder_attempt + 1],
                countdown=countdown,
            )

    asyncio.run(_run())


@app.task(bind=True, max_retries=3)
def send_evening_prompt(self, user_id: int, plan_date: str, attempt_count: int = 0):
    """Send evening review. plan_date is ISO. Schedules reminders at 1h and 3h."""
    d = date.fromisoformat(plan_date)
    try:
        asyncio.run(_send_evening(user_id, d, attempt_count))
        send_evening_reminder.apply_async(args=[user_id, plan_date], countdown=3600)
        send_evening_reminder.apply_async(args=[user_id, plan_date], countdown=3600 * 3)
    except Exception as exc:
        countdown = 2 ** (attempt_count + 1) * 60
        raise self.retry(exc=exc, countdown=countdown)


@app.task
def send_evening_reminder(user_id: int, plan_date: str):
    """Reminder to mark evening statuses (1h and 3h after evening prompt)."""
    async def _run():
        factory, engine = _get_async_session()
        d = date.fromisoformat(plan_date)
        async with factory() as session:
            r = await session.execute(
                select(Plan).where(Plan.user_id == user_id, Plan.date == d).options(selectinload(Plan.tasks).selectinload(Task.status))
            )
            plan = r.scalar_one_or_none()
            if not plan or not plan.tasks:
                await engine.dispose()
                return
            all_done = all(t.status for t in plan.tasks)
            if all_done:
                await engine.dispose()
                return
            r = await session.execute(select(User).where(User.id == user_id))
            user = r.scalar_one_or_none()
            if not user:
                await engine.dispose()
                return
        await engine.dispose()
        settings = Settings()
        bot = Bot(token=settings.telegram_bot_token)
        try:
            await bot.send_message(user.telegram_id, REMINDER_EVENING)
        finally:
            await bot.session.close()

    asyncio.run(_run())


@app.task
def dispatch_daily_notifications():
    """
    Run every 15 min: find users for whom it's 07:00 or 21:00 in their TZ,
    enqueue send_morning_prompt or send_evening_prompt.
    """
    async def _run():
        settings = Settings()
        factory, engine = _get_async_session()
        today = date.today()
        async with factory() as session:
            r = await session.execute(select(User))
            users = list(r.scalars().all())
            for user in users:
                try:
                    tz = ZoneInfo(user.timezone)
                except Exception:
                    tz = ZoneInfo("UTC")
                now = datetime.now(tz).time()
                mt, et = user.notify_morning_time, user.notify_evening_time
                if mt and (mt.hour == now.hour and mt.minute <= now.minute < mt.minute + 15):
                    r2 = await session.execute(
                        select(NotificationLog).where(
                            NotificationLog.user_id == user.id,
                            NotificationLog.type == TYPE_MORNING,
                            func.date(NotificationLog.created_at) == today,
                        ).limit(1)
                    )
                    if r2.scalar_one_or_none() is None:
                        send_morning_prompt.delay(user.id, today.isoformat(), 0)
                if et and (et.hour == now.hour and et.minute <= now.minute < et.minute + 15):
                    r2 = await session.execute(
                        select(NotificationLog).where(
                            NotificationLog.user_id == user.id,
                            NotificationLog.type == TYPE_EVENING,
                            func.date(NotificationLog.created_at) == today,
                        ).limit(1)
                    )
                    if r2.scalar_one_or_none() is None:
                        send_evening_prompt.delay(user.id, today.isoformat(), 0)
        await engine.dispose()

    asyncio.run(_run())
