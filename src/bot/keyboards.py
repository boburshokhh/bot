"""Keyboards for bot."""
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)


# Common timezones for /start (simplified list)
TZ_CHOICES = [
    ["Europe/Moscow", "Europe/Kyiv", "Europe/Minsk"],
    ["Europe/London", "Europe/Berlin", "Asia/Almaty"],
    ["Asia/Tbilisi", "Asia/Yerevan", "Asia/Tashkent"],
    ["UTC"],
]


def tz_keyboard(include_detect: bool = False) -> ReplyKeyboardMarkup:
    """Create timezone selection keyboard with optional auto-detect button."""
    rows = [
        [KeyboardButton(text=t) for t in row]
        for row in TZ_CHOICES
    ]
    if include_detect:
        # Add WebApp button for timezone detection
        from aiogram.types import WebAppInfo
        try:
            from src.config import Settings
            webapp_url = Settings().webhook_base_url.strip()
            if webapp_url:
                detect_url = f"{webapp_url.rstrip('/')}/timezone-detector"
                rows.append([
                    KeyboardButton(
                        text="🌍 Определить мой часовой пояс",
                        web_app=WebAppInfo(url=detect_url)
                    )
                ])
        except Exception:
            # Если не настроен webhook_base_url, просто не добавляем кнопку
            pass
    kb = ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    return kb


def morning_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Отправил ✅"), KeyboardButton(text="Пропустить сегодня ⏭")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def evening_inline_keyboard(task_ids: list[int]) -> InlineKeyboardMarkup:
    """One row per task: [✅] [⚠] [❌] [💬]. callback_data: task_done_<id>, task_partial_<id>, task_failed_<id>, task_comment_<id>."""
    rows = []
    for tid in task_ids:
        rows.append([
            InlineKeyboardButton(text="✅", callback_data=f"task_done_{tid}"),
            InlineKeyboardButton(text="⚠", callback_data=f"task_partial_{tid}"),
            InlineKeyboardButton(text="❌", callback_data=f"task_failed_{tid}"),
            InlineKeyboardButton(text="💬", callback_data=f"task_comment_{tid}"),
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def evening_done_keyboard() -> InlineKeyboardMarkup:
    """After all statuses: add day comment or finish."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить комментарий к дню", callback_data="day_comment")],
        [InlineKeyboardButton(text="Готово", callback_data="day_done")],
    ])


def webapp_keyboard(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть WebApp", web_app=WebAppInfo(url=url))],
        ]
    )


# --- Inline menu navigation (post-timezone) ---
# callback_data constants
MENU_MAIN = "menu_main"
MENU_PLAN = "menu_plan"
MENU_STATS = "menu_stats"
MENU_SETTINGS = "menu_settings"
MENU_SETTINGS_NOTIFY = "menu_settings_notify"
MENU_SETTINGS_INTERVALS = "menu_settings_intervals"

ACTION_HELP = "action_help"
ACTION_PLAN_ADD = "action_plan_add"
ACTION_TODAY = "action_today"
ACTION_HISTORY = "action_history"
ACTION_STATS = "action_stats"

ACTION_SETTINGS_TIMEZONE = "action_settings_timezone"
ACTION_SETTINGS_SET_MORNING = "action_settings_set_morning"
ACTION_SETTINGS_SET_EVENING = "action_settings_set_evening"
ACTION_SETTINGS_SET_INTERVAL = "action_settings_set_interval"
ACTION_SETTINGS_SET_ATTEMPTS = "action_settings_set_attempts"


def _nav_rows(*, back_to: str) -> list[list[InlineKeyboardButton]]:
    # Keep both buttons everywhere (per spec), even if both go to main.
    return [[
        InlineKeyboardButton(text="⬅️ Назад", callback_data=back_to),
        InlineKeyboardButton(text="🏠 Главное меню", callback_data=MENU_MAIN),
    ]]


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 План", callback_data=MENU_PLAN)],
        [InlineKeyboardButton(text="📊 Статистика", callback_data=MENU_STATS)],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data=MENU_SETTINGS)],
        [InlineKeyboardButton(text="❓ Помощь", callback_data=ACTION_HELP)],
    ])


def plan_submenu_keyboard() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="➕ Добавить план", callback_data=ACTION_PLAN_ADD)],
        [InlineKeyboardButton(text="📅 План на сегодня", callback_data=ACTION_TODAY)],
        [InlineKeyboardButton(text="📜 История", callback_data=ACTION_HISTORY)],
    ]
    rows += _nav_rows(back_to=MENU_MAIN)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def stats_submenu_keyboard() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="📈 Общая статистика", callback_data=ACTION_STATS)],
        [InlineKeyboardButton(text="📅 План на сегодня", callback_data=ACTION_TODAY)],
        [InlineKeyboardButton(text="📜 История", callback_data=ACTION_HISTORY)],
    ]
    rows += _nav_rows(back_to=MENU_MAIN)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def settings_submenu_keyboard() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="🌍 Часовой пояс", callback_data=ACTION_SETTINGS_TIMEZONE)],
        [InlineKeyboardButton(text="⏰ Время уведомлений", callback_data=MENU_SETTINGS_NOTIFY)],
        [InlineKeyboardButton(text="🔄 Интервалы", callback_data=MENU_SETTINGS_INTERVALS)],
    ]
    rows += _nav_rows(back_to=MENU_MAIN)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def notify_time_submenu_keyboard() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="🌅 Настроить утреннее время", callback_data=ACTION_SETTINGS_SET_MORNING)],
        [InlineKeyboardButton(text="🌆 Настроить вечернее время", callback_data=ACTION_SETTINGS_SET_EVENING)],
    ]
    rows += _nav_rows(back_to=MENU_SETTINGS)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def intervals_submenu_keyboard() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="⏱️ Настроить интервал", callback_data=ACTION_SETTINGS_SET_INTERVAL)],
        [InlineKeyboardButton(text="🔢 Настроить максимум попыток", callback_data=ACTION_SETTINGS_SET_ATTEMPTS)],
    ]
    rows += _nav_rows(back_to=MENU_SETTINGS)
    return InlineKeyboardMarkup(inline_keyboard=rows)
