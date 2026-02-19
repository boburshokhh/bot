"""FSM states for planning flow."""
from aiogram.fsm.state import State, StatesGroup


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
