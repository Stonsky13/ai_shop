from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User, Payment
from app.utils.utils import utcnow_naive, add_days, is_premium_active


logger = logging.getLogger(__name__)


class UserService:
    async def get_or_create_user(self, session: AsyncSession, tg_id: int, username: str) -> User:
        q = await session.execute(select(User).where(User.tg_id == tg_id))
        user = q.scalar_one_or_none()
        if user:
            if username and user.username != username:
                user.username = username
                await session.commit()
            return user

        user = User(tg_id=tg_id, username=username or "", premium_until=None)
        session.add(user)
        await session.commit()
        return user

    async def activate_subscription(self, session: AsyncSession, tg_id: int, days: int) -> datetime:
        q = await session.execute(select(User).where(User.tg_id == tg_id))
        user = q.scalar_one_or_none()
        if not user:
            user = User(tg_id=tg_id, username="", premium_until=None)
            session.add(user)
            await session.commit()

        now = utcnow_naive()
        base = user.premium_until if (user.premium_until and user.premium_until > now) else now
        user.premium_until = add_days(base, days)
        await session.commit()
        return user.premium_until

    async def get_status_text(self, session: AsyncSession, tg_id: int) -> str:
        q = await session.execute(select(User).where(User.tg_id == tg_id))
        user = q.scalar_one_or_none()
        if not user or not is_premium_active(user.premium_until):
            return "Статус: доступа нет. Купи подписку командой /buy"
        return f"Статус: активен до {user.premium_until.strftime('%Y-%m-%d %H:%M:%S')} (UTC)"


class PaymentService:
    async def create_payment_record(
        self,
        session: AsyncSession,
        payment_id: str,
        tg_id: int,
        amount_rub: float,
        status: str,
        confirmation_url: str,
    ) -> Payment:
        p = Payment(
            payment_id=payment_id,
            tg_id=tg_id,
            amount_rub=amount_rub,
            status=status,
            confirmation_url=confirmation_url,
            created_at=utcnow_naive(),
            updated_at=utcnow_naive(),
        )
        session.add(p)
        await session.commit()
        return p

    async def get_last_payment(self, session: AsyncSession, tg_id: int) -> Payment | None:
        q = await session.execute(
            select(Payment).where(Payment.tg_id == tg_id).order_by(Payment.created_at.desc())
        )
        return q.scalars().first()

    async def update_payment_status(self, session: AsyncSession, payment_id: str, status: str) -> None:
        await session.execute(
            update(Payment)
            .where(Payment.payment_id == payment_id)
            .values(status=status, updated_at=utcnow_naive())
        )
        await session.commit()

    async def get_payment_by_id(self, session: AsyncSession, payment_id: str) -> Payment | None:
        q = await session.execute(select(Payment).where(Payment.payment_id == payment_id))
        return q.scalar_one_or_none()


class PaymentPoller:
    def __init__(
        self,
        attempts: int,
        interval_sec: int,
        yookassa_get_status_fn,
        on_succeeded_async_fn,
        on_status_update_async_fn,
    ) -> None:
        self._attempts = attempts
        self._interval = interval_sec
        self._get_status = yookassa_get_status_fn
        self._on_succeeded = on_succeeded_async_fn
        self._on_status_update = on_status_update_async_fn

    async def run(self, payment_id: str) -> None:
        for i in range(self._attempts):
            try:
                info = self._get_status(payment_id)
                status = (info.get("status") or "").lower()
                paid = bool(info.get("paid", False))

                await self._on_status_update(payment_id, status)

                if paid and status == "succeeded":
                    await self._on_succeeded(payment_id, info)
                    return

                if status in {"canceled"}:
                    return

            except Exception:
                logger.exception("Payment polling failed for %s (attempt %s/%s)", payment_id, i + 1, self._attempts)

            await asyncio.sleep(self._interval)
