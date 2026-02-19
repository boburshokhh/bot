"""Message templates."""
from datetime import date, time

MORNING_PROMPT = """Доброе утро! Напиши план на сегодня — каждый пункт с новой строки. Пример:

1. Прочитать отчёт
2. Встреча в 11:00
3. Тренировка"""

EVENING_INTRO = "План на сегодня:\n\n"
EVENING_AFTER_STATUSES = "\n\nНажми на статус для каждой задачи. По желанию оставь комментарий."
EVENING_DAY_COMMENT_PROMPT = "Итог: {done}/{total} выполнено ({percent}%). Хотите добавить комментарий к дню?"

WELCOME = "Привет! Я бот для утреннего планирования и вечерней сверки. Выбери часовой пояс:"
TZ_SET = "Часовой пояс сохранён. Завтра в 07:00 пришлю запрос плана."
TIMEZONE_CHOOSE_PROMPT = "Выбери часовой пояс:"
PLAN_SAVED = "План сохранён. Вечером напомню сверить выполнение."
PLAN_SKIPPED = "Ок, пропускаем сегодня. Завтра снова спрошу план."
PLAN_OPENED_MANUALLY = "Открываю ввод плана на сегодня."
PLAN_ALREADY_EXISTS_TODAY = "План на сегодня уже есть. Посмотреть можно командой /today."
REMINDER_MORNING = "Напоминание: напиши план на сегодня (каждый пункт с новой строки)."
REMINDER_EVENING = "Напоминание: отметь статусы по плану на сегодня."
COMMANDS_OVERVIEW = (
    "Команды управления:\n"
    "/plan - добавить план на сегодня вручную\n"
    "/today - посмотреть план на сегодня\n"
    "/history YYYY-MM - история планов за месяц\n"
    "/stats - общая статистика\n"
    "/settings - текущие настройки\n"
    "/time - время на сервере бота и твой часовой пояс\n"
    "/timezone - сменить часовой пояс\n"
    "/set_morning HH:MM - время утреннего сообщения\n"
    "/set_evening HH:MM - время вечернего сообщения\n"
    "/set_interval MIN - интервал напоминаний, если план не добавлен\n"
    "/set_attempts N - максимум повторных напоминаний\n"
    "/webapp - открыть веб-панель управления\n"
    "/help - показать список команд"
)


def format_settings(
    timezone: str,
    morning_time: time,
    evening_time: time,
    reminder_interval_minutes: int,
    reminder_max_attempts: int,
) -> str:
    return (
        "Текущие настройки:\n"
        f"• Часовой пояс: {timezone}\n"
        f"• Утреннее напоминание: {morning_time.strftime('%H:%M')}\n"
        f"• Вечернее напоминание: {evening_time.strftime('%H:%M')}\n"
        f"• Интервал повторов утром: {reminder_interval_minutes} мин\n"
        f"• Повторов максимум: {reminder_max_attempts}\n\n"
        "Используй /help для списка команд или /webapp для веб-управления."
    )


def format_evening_plan(plan_date: date, tasks_with_status: list[tuple[str, str | None]]) -> str:
    """Format plan for evening: task text + current status if any."""
    lines = [f"План на {plan_date}:\n"]
    for i, (text, status) in enumerate(tasks_with_status, 1):
        icon = {"done": "✅", "partial": "⚠", "failed": "❌"}.get(status, "—") if status else "—"
        lines.append(f"{i}. {text} {icon}")
    return "\n".join(lines) + EVENING_AFTER_STATUSES
