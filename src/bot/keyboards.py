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


def reminder_type_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Ежедневно")],
            [KeyboardButton(text="Раз в месяц")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def onboarding_time_keyboard(default_time: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"Оставить {default_time}")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def morning_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Отправил ✅"), KeyboardButton(text="Пропустить сегодня ⏭")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def evening_inline_keyboard(tasks_with_status: list[tuple[int, str | None]]) -> InlineKeyboardMarkup:
    """One row per task that is not 'done': [✅] [⚠] [❌] [💬]. For status 'done' no buttons (cannot change)."""
    rows = []
    for tid, status_enum in tasks_with_status:
        if status_enum == "done":
            continue
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


# --- Reply keyboard menu (post-timezone) ---
# Button text constants for menu navigation
BTN_PLAN = "📝 План"
BTN_STATS = "📊 Статистика"
BTN_SETTINGS = "⚙️ Настройки"
BTN_HELP = "❓ Помощь"
BTN_PLAN_ADD = "➕ Добавить план"
BTN_TODAY = "📅 План на сегодня"
BTN_DELETE_PLAN = "🗑️ Удалить план"
BTN_HISTORY = "📜 История"
BTN_STATS_OVERVIEW = "📈 Общая статистика"
BTN_NAV_BACK = "⬅️ Назад"
BTN_NAV_MAIN = "🏠 Главное меню"
BTN_SETTINGS_TZ = "🌍 Часовой пояс"
BTN_SETTINGS_NOTIFY = "⏰ Время уведомлений"
BTN_SETTINGS_INTERVALS = "🔄 Интервалы"
BTN_SET_MORNING = "🌅 Настроить утреннее время"
BTN_SET_EVENING = "🌆 Настроить вечернее время"
BTN_SET_INTERVAL = "⏱️ Настроить интервал"
BTN_SET_ATTEMPTS = "🔢 Настроить максимум попыток"
BTN_RESET_NOTIFICATIONS = "🔄 Сбросить отправки за сегодня"


def _nav_row_reply() -> list[list[KeyboardButton]]:
    return [[
        KeyboardButton(text=BTN_NAV_BACK),
        KeyboardButton(text=BTN_NAV_MAIN),
    ]]


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_PLAN)],
            [KeyboardButton(text=BTN_STATS)],
            [KeyboardButton(text=BTN_SETTINGS)],
            [KeyboardButton(text=BTN_HELP)],
        ],
        resize_keyboard=True,
    )


def plan_submenu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_PLAN_ADD)],
            [KeyboardButton(text=BTN_TODAY)],
            [KeyboardButton(text=BTN_DELETE_PLAN)],
            [KeyboardButton(text=BTN_HISTORY)],
            *_nav_row_reply(),
        ],
        resize_keyboard=True,
    )


def stats_submenu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_STATS_OVERVIEW)],
            [KeyboardButton(text=BTN_TODAY)],
            [KeyboardButton(text=BTN_HISTORY)],
            *_nav_row_reply(),
        ],
        resize_keyboard=True,
    )


def settings_submenu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_SETTINGS_TZ)],
            [KeyboardButton(text=BTN_SETTINGS_NOTIFY)],
            [KeyboardButton(text=BTN_SETTINGS_INTERVALS)],
            [KeyboardButton(text=BTN_RESET_NOTIFICATIONS)],
            *_nav_row_reply(),
        ],
        resize_keyboard=True,
    )


def notify_time_submenu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_SET_MORNING)],
            [KeyboardButton(text=BTN_SET_EVENING)],
            *_nav_row_reply(),
        ],
        resize_keyboard=True,
    )


def intervals_submenu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_SET_INTERVAL)],
            [KeyboardButton(text=BTN_SET_ATTEMPTS)],
            *_nav_row_reply(),
        ],
        resize_keyboard=True,
    )


def custom_reminder_inline_keyboard(reminder_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Выполнено сегодня", callback_data=f"crem_done_{reminder_id}")],
            [
                InlineKeyboardButton(text="🔕 Отключить", callback_data=f"crem_off_{reminder_id}"),
                InlineKeyboardButton(text="🗑 Удалить", callback_data=f"crem_del_{reminder_id}"),
            ],
        ]
    )

def custom_reminder_off_keyboard(reminder_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔔 Включить", callback_data=f"crem_on_{reminder_id}")],
            [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"crem_del_{reminder_id}")],
        ]
    )
