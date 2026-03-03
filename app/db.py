from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text


class Base(DeclarativeBase):
    pass


def build_engine(sqlite_path: str) -> AsyncEngine:
    folder = os.path.dirname(sqlite_path)
    if folder:
        Path(folder).mkdir(parents=True, exist_ok=True)

    url = f"sqlite+aiosqlite:///{sqlite_path}"
    return create_async_engine(url, future=True, echo=False)


def build_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def init_db(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("PRAGMA journal_mode=WAL;"))
        await conn.execute(text("PRAGMA foreign_keys=ON;"))
        from app import models  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)
