from aiogram import BaseMiddleware
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession


class DbSessionMiddleware(BaseMiddleware):
    def __init__(self, sessionmaker):
        self._sessionmaker = sessionmaker

    async def __call__(self, handler, event, data):
        async with self._sessionmaker() as session:
            try:
                data["db"] = session
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise