"""Async database session and engine."""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from src.config import Settings


class Base(DeclarativeBase):
    pass


def get_engine(database_url: str | None = None):
    url = database_url or Settings().database_url
    return create_async_engine(
        url,
        echo=False,
        pool_pre_ping=True,
    )


def init_async_engine(database_url: str | None = None):
    engine = get_engine(database_url)
    return engine


async_session_factory: async_sessionmaker[AsyncSession] | None = None


def set_async_session_factory(engine):
    global async_session_factory
    async_session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    if not async_session_factory:
        raise RuntimeError("Async session factory not initialized. Call set_async_session_factory(engine) first.")
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
