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

BOTS_CANT_SEND_TO_BOTS = "bots can't send messages to bots"


def _is_non_retryable_telegram_error(exc: BaseException) -> bool:
    """True if Telegram error should not be retried (e.g. Forbidden: bots can't send to bots)."""
    msg = str(exc).strip()
    return BOTS_CANT_SEND_TO_BOTS in msg or "Forbidden:" in msg and "bot" in msg.lower()


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


async def _send_error_to_user(user_id: int, notification_type: str, error_text: str) -> None:
    """Send server error message to user in Telegram on final Celery task failure."""
    factory, engine = _get_async_session()
    try:
        async with factory() as session:
            r = await session.execute(select(User).where(User.id == user_id))
            user = r.scalar_one_or_none()
            if not user or not user.telegram_id:
                return
            telegram_id = user.telegram_id
    finally:
        await engine.dispose()

    settings = Settings()
    bot = Bot(token=settings.telegram_bot_token)
    try:
        ntype = "утреннее" if notification_type == "morning" else "вечернее"
        await bot.send_message(
            telegram_id,
            f"Не удалось отправить {ntype} напоминание: {error_text}"
        )
    except Exception as e:
        logger.exception("Failed to send error notification to user_id=%s: %s", user_id, e)
    finally:
        await bot.session.close()


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
                session,
                user_id,
                TYPE_MORNING,
                STATUS_RETRIED if attempt_count > 0 else STATUS_FAILED,
                {"date": plan_date.isoformat(), "error": str(e), "attempt": attempt_count},
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
                session, user_id, TYPE_EVENING, STATUS_SENT, {"plan_id": plan_id, "date": plan_date.isoformat(), "attempt": attempt_count}
            )
            await session.commit()
        await engine2.dispose()
    except Exception as e:
        logger.exception("Evening send failed user_id=%s: %s", user_id, e)
        factory2, engine2 = _get_async_session()
        async with factory2() as session:
            await log_notification(
                session,
                user_id,
                TYPE_EVENING,
                STATUS_RETRIED if attempt_count > 0 else STATUS_FAILED,
                {"date": plan_date.isoformat(), "error": str(e), "attempt": attempt_count},
            )
            await session.commit()
        await engine2.dispose()
        raise
    finally:
        await bot.session.close()


@app.task(bind=True, max_retries=3)
def send_morning_prompt(self, user_id: int, plan_date: str, _attempt_count: int = 0):
    """Send morning plan request. plan_date is ISO (YYYY-MM-DD). Attempt number from self.request.retries."""
    d = date.fromisoformat(plan_date)
    attempt = self.request.retries
    try:
        asyncio.run(_send_morning(user_id, d, attempt))
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
        if _is_non_retryable_telegram_error(exc):
            logger.warning("Morning prompt non-retryable for user_id=%s: %s", user_id, exc)
            asyncio.run(_send_error_to_user(user_id, "morning", str(exc)))
            raise
        countdown = 2 ** (attempt + 1) * 60
        try:
            self.retry(exc=exc, countdown=countdown)
        except self.MaxRetriesExceededError:
            asyncio.run(_send_error_to_user(user_id, "morning", str(exc)))
            raise


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
        payload_sent = {"date": d.isoformat(), "reminder_attempt": reminder_attempt}
        try:
            await bot.send_message(telegram_id, REMINDER_MORNING, reply_markup=morning_reply_keyboard())
            await set_awaiting_plan(settings.redis_url, settings.telegram_bot_token, telegram_id, d)
        except Exception as e:
            logger.exception("Morning reminder send failed user_id=%s attempt=%s: %s", user_id, reminder_attempt, e)
            factory2, engine2 = _get_async_session()
            async with factory2() as session:
                await log_notification(
                    session,
                    user_id,
                    TYPE_MORNING,
                    STATUS_FAILED,
                    {"date": d.isoformat(), "reminder_attempt": reminder_attempt, "error": str(e)},
                )
                await session.commit()
            await engine2.dispose()
            raise
        finally:
            await bot.session.close()

        factory2, engine2 = _get_async_session()
        async with factory2() as session:
            await log_notification(session, user_id, TYPE_MORNING, STATUS_SENT, payload_sent)
            await session.commit()
        await engine2.dispose()

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
def send_evening_prompt(self, user_id: int, plan_date: str, _attempt_count: int = 0):
    """Send evening review. plan_date is ISO. Schedules reminders at 1h and 3h. Attempt from self.request.retries."""
    d = date.fromisoformat(plan_date)
    attempt = self.request.retries
    try:
        asyncio.run(_send_evening(user_id, d, attempt))
        send_evening_reminder.apply_async(args=[user_id, plan_date], countdown=3600)
        send_evening_reminder.apply_async(args=[user_id, plan_date], countdown=3600 * 3)
    except Exception as exc:
        if _is_non_retryable_telegram_error(exc):
            logger.warning("Evening prompt non-retryable for user_id=%s: %s", user_id, exc)
            asyncio.run(_send_error_to_user(user_id, "evening", str(exc)))
            raise
        countdown = 2 ** (attempt + 1) * 60
        try:
            self.retry(exc=exc, countdown=countdown)
        except self.MaxRetriesExceededError:
            asyncio.run(_send_error_to_user(user_id, "evening", str(exc)))
            raise


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


def _get_dispatch_window() -> int:
    """Return configured dispatch window in minutes (from env DISPATCH_WINDOW_MINUTES, default 10)."""
    try:
        return max(1, int(Settings().dispatch_window_minutes))
    except Exception:
        return 10


def _in_dispatch_window(now_minutes_since_midnight: int, target_time, window_minutes: int) -> bool:
    """True if now is within window_minutes after target_time (in same day)."""
    target_m = target_time.hour * 60 + target_time.minute
    delta = (now_minutes_since_midnight - target_m) % 1440
    return 0 <= delta < window_minutes


@app.task
def dispatch_daily_notifications():
    """
    Run every minute: find users for whom it's morning/evening time in their TZ,
    enqueue send_morning_prompt or send_evening_prompt.
    Uses user timezone for 'today' and for duplicate check. No UTC fallback to avoid wrong delivery time.
    """
    async def _run():
        window = _get_dispatch_window()
        factory, engine = _get_async_session()
        async with factory() as session:
            r = await session.execute(select(User))
            users = list(r.scalars().all())
            logger.info("dispatch_daily_notifications: checking %d user(s), window=%d min", len(users), window)
            for user in users:
                try:
                    tz = ZoneInfo(user.timezone)
                except Exception as e:
                    logger.warning(
                        "Skipping notifications for user_id=%s: timezone '%s' invalid or tzdata missing: %s",
                        user.id,
                        user.timezone,
                        e,
                    )
                    continue
                now = datetime.now(tz)
                user_today = now.date()
                now_m = now.hour * 60 + now.minute
                mt, et = user.notify_morning_time, user.notify_evening_time
                logger.debug(
                    "user_id=%s tz=%s local_time=%s morning=%s evening=%s",
                    user.id, user.timezone,
                    now.strftime("%H:%M"),
                    mt.strftime("%H:%M") if mt else "None",
                    et.strftime("%H:%M") if et else "None",
                )
                if mt and _in_dispatch_window(now_m, mt, window):
                    r2 = await session.execute(
                        select(NotificationLog).where(
                            NotificationLog.user_id == user.id,
                            NotificationLog.type == TYPE_MORNING,
                            NotificationLog.status == STATUS_SENT,
                            NotificationLog.payload["date"].astext == user_today.isoformat(),
                        ).limit(1)
                    )
                    sent_today = r2.scalar_one_or_none() is not None
                    if not sent_today:
                        logger.info("Dispatching morning prompt for user_id=%s date=%s", user.id, user_today)
                        send_morning_prompt.delay(user.id, user_today.isoformat(), 0)
                    else:
                        logger.info("Skipping morning dispatch for user_id=%s date=%s (already have log)", user.id, user_today)
                if et and _in_dispatch_window(now_m, et, window):
                    r2 = await session.execute(
                        select(NotificationLog).where(
                            NotificationLog.user_id == user.id,
                            NotificationLog.type == TYPE_EVENING,
                            NotificationLog.status == STATUS_SENT,
                            NotificationLog.payload["date"].astext == user_today.isoformat(),
                        ).limit(1)
                    )
                    sent_today = r2.scalar_one_or_none() is not None
                    if not sent_today:
                        logger.info("Dispatching evening prompt for user_id=%s date=%s", user.id, user_today)
                        send_evening_prompt.delay(user.id, user_today.isoformat(), 0)
                    else:
                        logger.info("Skipping evening dispatch for user_id=%s date=%s (already have log)", user.id, user_today)
        await engine.dispose()

    asyncio.run(_run())
