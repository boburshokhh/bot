"""Message templates."""
from datetime import date

MORNING_PROMPT = """Доброе утро! Напиши план на сегодня — каждый пункт с новой строки. Пример:

1. Прочитать отчёт
2. Встреча в 11:00
3. Тренировка"""

EVENING_INTRO = "План на сегодня:\n\n"
EVENING_AFTER_STATUSES = "\n\nНажми на статус для каждой задачи. По желанию оставь комментарий."
EVENING_DAY_COMMENT_PROMPT = "Итог: {done}/{total} выполнено ({percent}%). Хотите добавить комментарий к дню?"

WELCOME = "Привет! Я бот для утреннего планирования и вечерней сверки. Выбери часовой пояс:"
TZ_SET = "Часовой пояс сохранён. Завтра в 07:00 пришлю запрос плана."
PLAN_SAVED = "План сохранён. Вечером напомню сверить выполнение."
PLAN_SKIPPED = "Ок, пропускаем сегодня. Завтра снова спрошу план."
REMINDER_MORNING = "Напоминание: напиши план на сегодня (каждый пункт с новой строки)."
REMINDER_EVENING = "Напоминание: отметь статусы по плану на сегодня."


def format_evening_plan(plan_date: date, tasks_with_status: list[tuple[str, str | None]]) -> str:
    """Format plan for evening: task text + current status if any."""
    lines = [f"План на {plan_date}:\n"]
    for i, (text, status) in enumerate(tasks_with_status, 1):
        icon = {"done": "✅", "partial": "⚠", "failed": "❌"}.get(status, "—") if status else "—"
        lines.append(f"{i}. {text} {icon}")
    return "\n".join(lines) + EVENING_AFTER_STATUSES
