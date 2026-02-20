"""SQLAlchemy models for planning bot."""
from __future__ import annotations

from datetime import date, datetime, time
from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, Text, Time, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.session import Base


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    timezone: Mapped[str] = mapped_column(Text, nullable=False, default="UTC")
    notify_morning_time: Mapped[time] = mapped_column(Time, nullable=False, default=time(7, 0))
    notify_evening_time: Mapped[time] = mapped_column(Time, nullable=False, default=time(21, 0))
    morning_reminder_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    morning_reminder_max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    plans: Mapped[list["Plan"]] = relationship("Plan", back_populates="user", cascade="all, delete-orphan")
    notification_logs: Mapped[list["NotificationLog"]] = relationship(
        "NotificationLog", back_populates="user", cascade="all, delete-orphan"
    )
    custom_reminders: Mapped[list["CustomReminder"]] = relationship(
        "CustomReminder", back_populates="user", cascade="all, delete-orphan"
    )


class Plan(Base):
    __tablename__ = "plan"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_plan_user_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)

    user: Mapped["User"] = relationship("User", back_populates="plans")
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="plan", cascade="all, delete-orphan", order_by="Task.position")


class Task(Base):
    __tablename__ = "task"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(Integer, ForeignKey("plan.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)

    plan: Mapped["Plan"] = relationship("Plan", back_populates="tasks")
    status: Mapped["TaskStatus | None"] = relationship(
        "TaskStatus", back_populates="task", uselist=False, cascade="all, delete-orphan"
    )


class TaskStatus(Base):
    __tablename__ = "task_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("task.id", ondelete="CASCADE"), nullable=False, unique=True)
    status_enum: Mapped[str] = mapped_column(Text, nullable=False)  # done, partial, failed
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    responded_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)

    task: Mapped["Task"] = relationship("Task", back_populates="status")


class NotificationLog(Base):
    __tablename__ = "notification_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)  # morning, evening
    status: Mapped[str] = mapped_column(Text, nullable=False)  # sent, failed, retried
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)

    user: Mapped["User"] = relationship("User", back_populates="notification_logs")


class CustomReminder(Base):
    __tablename__ = "custom_reminder"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    time_of_day: Mapped[time] = mapped_column(Time, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    
    repeat_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    max_attempts_per_day: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    
    # State for the current day
    cycle_local_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    attempts_sent_today: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    done_today: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    
    # Scheduling
    next_fire_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True, index=True)
    last_sent_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    
    # Control & Concurrency
    locked_until_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped["User"] = relationship("User", back_populates="custom_reminders")
