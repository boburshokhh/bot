"""FSM states for planning flow."""
from aiogram.fsm.state import State, StatesGroup


class OnboardingStates(StatesGroup):
    awaiting_timezone = State()
    awaiting_morning_time = State()
    awaiting_evening_time = State()


class PlanStates(StatesGroup):
    idle = State()
    awaiting_plan = State()
    awaiting_confirmation = State()
    editing_plan = State()
    awaiting_comment = State()  # data: task_id for which we wait comment


class SettingsStates(StatesGroup):
    awaiting_morning_time = State()
    awaiting_evening_time = State()
    awaiting_interval_minutes = State()
    awaiting_max_attempts = State()


class MenuStates(StatesGroup):
    main = State()
    plan = State()
    stats = State()
    settings = State()
    settings_notify = State()
    settings_intervals = State()


class ReminderStates(StatesGroup):
    awaiting_type = State()
    awaiting_day_of_month = State()
    awaiting_time = State()
    awaiting_description = State()
    awaiting_interval = State()
    awaiting_max_attempts = State()
