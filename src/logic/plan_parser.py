"""Parse multiline plan text into list of task strings. Idempotent-friendly: no duplicates by text."""
from __future__ import annotations

import re
from typing import List

# Max length per task and total plan size (chars) for validation
MAX_TASK_LENGTH = 500
MAX_PLAN_LENGTH = 10_000
MAX_TASKS = 50


def parse_plan_lines(raw: str) -> List[str]:
    """
    Parse multiline text into list of non-empty task strings.
    - Splits by newline (\\n, \\r\\n).
    - Strips whitespace from each line.
    - Drops empty lines.
    - Optionally strips leading numbering like "1.", "2)", "3 ".
    """
    if not raw or not raw.strip():
        return []
    lines = re.split(r"[\r\n]+", raw)
    tasks: List[str] = []
    for line in lines:
        s = line.strip()
        if not s:
            continue
        # Strip leading numbering: "1.", "2)", "3 ", " 4. "
        s = re.sub(r"^\s*\d+[.)]\s*", "", s).strip()
        if not s:
            continue
        if len(s) > MAX_TASK_LENGTH:
            s = s[:MAX_TASK_LENGTH]
        tasks.append(s)
    return tasks[:MAX_TASKS]


def validate_plan_text(raw: str) -> tuple[bool, str]:
    """
    Validate plan input: length and sanity.
    Returns (ok, error_message).
    """
    if not raw or not raw.strip():
        return False, "План не может быть пустым."
    if len(raw) > MAX_PLAN_LENGTH:
        return False, f"План слишком длинный (максимум {MAX_PLAN_LENGTH} символов)."
    tasks = parse_plan_lines(raw)
    if not tasks:
        return False, "Не удалось выделить ни одной задачи. Напиши каждый пункт с новой строки."
    if len(tasks) > MAX_TASKS:
        return False, f"Слишком много задач (максимум {MAX_TASKS})."
    return True, ""
