"""Celery app with Redis broker."""
from celery import Celery
from celery.schedules import crontab

from src.config import Settings

settings = Settings()

app = Celery(
    "planning_bot",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["src.scheduler.tasks"],
)
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    beat_schedule={
        "dispatch-daily-notifications": {
            "task": "src.scheduler.tasks.dispatch_daily_notifications",
            "schedule": crontab(minute="*"),
        },
        "dispatch-custom-reminders": {
            "task": "src.scheduler.tasks.dispatch_custom_reminders",
            "schedule": crontab(minute="*"),
        },
    },
)
