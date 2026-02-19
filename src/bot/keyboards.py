"""Keyboards for bot."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton


# Common timezones for /start (simplified list)
TZ_CHOICES = [
    ["Europe/Moscow", "Europe/Kyiv", "Europe/Minsk"],
    ["Europe/London", "Europe/Berlin", "Asia/Almaty"],
    ["Asia/Tbilisi", "Asia/Yerevan", "Asia/Tashkent"],
    ["UTC"],
]


def tz_keyboard() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t) for t in row]
            for row in TZ_CHOICES
        ],
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
