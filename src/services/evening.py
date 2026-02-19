"""Evening review: task statuses and comments."""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Task, TaskStatus

# Status enum values
DONE = "done"
PARTIAL = "partial"
FAILED = "failed"


async def set_task_status(
    session: AsyncSession,
    task_id: int,
    status_enum: str,
    comment: str | None = None,
) -> TaskStatus | None:
    r = await session.execute(select(TaskStatus).where(TaskStatus.task_id == task_id))
    ts = r.scalar_one_or_none()
    if ts:
        ts.status_enum = status_enum
        if comment is not None:
            ts.comment = comment
        ts.responded_at = datetime.utcnow()
    else:
        ts = TaskStatus(task_id=task_id, status_enum=status_enum, comment=comment)
        session.add(ts)
    await session.flush()
    return ts


async def update_task_comment(session: AsyncSession, task_id: int, comment: str | None) -> TaskStatus | None:
    """Update only comment; keep existing status."""
    r = await session.execute(select(TaskStatus).where(TaskStatus.task_id == task_id))
    ts = r.scalar_one_or_none()
    if ts:
        ts.comment = comment
        ts.responded_at = datetime.utcnow()
        await session.flush()
        return ts
    # No status yet, create with done
    ts = TaskStatus(task_id=task_id, status_enum=DONE, comment=comment)
    session.add(ts)
    await session.flush()
    return ts


async def get_completion_for_plan(session: AsyncSession, plan_id: int) -> tuple[int, int, int]:
    """
    Returns (done_count, total_count, percent).
    'done' counts as full, 'partial' as half, 'failed' as 0.
    """
    from src.db.models import Task

    r = await session.execute(
        select(Task.id, TaskStatus.status_enum)
        .select_from(Task)
        .outerjoin(TaskStatus, TaskStatus.task_id == Task.id)
        .where(Task.plan_id == plan_id)
        .order_by(Task.position)
    )
    rows = r.all()
    total = len(rows)
    if total == 0:
        return 0, 0, 0
    done_count = 0
    for _task_id, status in rows:
        if status == DONE:
            done_count += 1
        elif status == PARTIAL:
            done_count += 0.5
    percent = int(round(100 * done_count / total))
    return int(done_count), total, percent
