"""Bot handlers."""
from aiogram import Router

from src.bot.handlers import common, evening, menu, plan, start, stats

router = Router()
router.include_router(start.router)
router.include_router(menu.router)
router.include_router(plan.router)
router.include_router(evening.router)
router.include_router(stats.router)
router.include_router(common.router)
