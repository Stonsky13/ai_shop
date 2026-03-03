from __future__ import annotations

from typing import Callable, Awaitable, Any
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession


class DbSessionMiddleware(BaseMiddleware):
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        super().__init__()
        self._sm = sessionmaker

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with self._sm() as session:
            data["db"] = session
            return await handler(event, data)
