"""Bot handlers."""
from aiogram import Router

from src.bot.handlers import common, evening, plan, start, stats

router = Router()
router.include_router(start.router, tags=["start"])
router.include_router(plan.router, tags=["plan"])
router.include_router(evening.router, tags=["evening"])
router.include_router(stats.router, tags=["stats"])
router.include_router(common.router, tags=["common"])
