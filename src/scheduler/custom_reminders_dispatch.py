import asyncio
from datetime import datetime, timezone
from aiogram import Bot
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import CustomReminder
from src.services.reminders import compute_next_daily_fire_utc
from src.scheduler.tasks import _get_async_session

import logging
from datetime import timedelta
logger = logging.getLogger(__name__)

async def dispatch_custom_reminders_async():
    now_utc = datetime.now(timezone.utc)
    factory, engine = _get_async_session()
    
    try:
        async with factory() as session:
            # Find due reminders that are enabled and not locked or lock expired
            r = await session.execute(
                select(CustomReminder).where(
                    CustomReminder.enabled == True,
                    CustomReminder.next_fire_at_utc <= now_utc.replace(tzinfo=None),
                    (CustomReminder.locked_until_utc == None) | (CustomReminder.locked_until_utc <= now_utc.replace(tzinfo=None))
                )
            )
            reminders = list(r.scalars().all())
            
            if not reminders:
                return
                
            logger.info(f"Found {len(reminders)} due custom reminders.")
            
            for reminder in reminders:
                # Lock for 2 minutes to prevent duplicate sends
                reminder.locked_until_utc = (now_utc + timedelta(minutes=2)).replace(tzinfo=None)
                
            await session.commit()
            
            # Now trigger the actual send tasks
            from src.scheduler.tasks import send_custom_reminder
            for reminder in reminders:
                send_custom_reminder.delay(reminder.id)
    finally:
        await engine.dispose()