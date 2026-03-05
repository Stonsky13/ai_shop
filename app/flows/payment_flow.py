from __future__ import annotations

import asyncio
import logging

from aiogram import Bot

from sqlalchemy.ext.asyncio import AsyncSession
from app.config import Settings
from app.clients.yookassa_client import YooKassaClient
from app.clients.sheets_client import SheetsClient
from app.services.services import UserService, PaymentService, PaymentPoller

logger = logging.getLogger(__name__)

class PaymentFlow:
    def __init__(
        self,
        settings: Settings,
        yk: YooKassaClient,
        sheets: SheetsClient,
        user_svc: UserService,
        pay_svc: PaymentService,
        bot: Bot,
        poller: PaymentPoller,
    ) -> None:
        self._settings = settings
        self._yk = yk
        self._sheets = sheets
        self._user_svc = user_svc
        self._pay_svc = pay_svc
        self._bot = bot
        self._poller = poller

        self._tasks: dict[str, asyncio.Task] = {}

    async def create_and_start_polling(self, db: AsyncSession, tg_id: int, username: str, chat_id: int) -> str:
        description = f"AI-ассистент на {self._settings.subscription_days} дней для tg_id={tg_id}"
        created = self._yk.create_payment(
            amount_rub=self._settings.subscription_price_rub,
            description=description,
            tg_id=tg_id,
            username=username,
        )

        payment_id = created["payment_id"]
        status = created["status"]
        url = created["confirmation_url"]

        await self._pay_svc.create_payment_record(
            db,
            payment_id=payment_id,
            tg_id=tg_id,
            amount_rub=self._settings.subscription_price_rub,
            status=status or "pending",
            confirmation_url=url,
        )

        self._sheets.log_event(tg_id, username, "payment_created", {"payment_id": payment_id, "status": status})

        if payment_id not in self._tasks or self._tasks[payment_id].done():
            t = asyncio.create_task(self._poller.run(payment_id))
            self._tasks[payment_id] = t

        return url

    async def check_last_payment(self, db: AsyncSession, tg_id: int, username: str, chat_id: int) -> str:
        last = await self._pay_svc.get_last_payment(db, tg_id)
        if not last:
            return "Платежей не найдено. Создай оплату: /buy"

        info = self._yk.get_payment(last.payment_id)
        status = (info.get("status") or "").lower()
        paid = bool(info.get("paid", False))

        await self._pay_svc.update_payment_status(db, last.payment_id, status or last.status)
        self._sheets.log_event(tg_id, username, "payment_checked", {"payment_id": last.payment_id, "status": status, "paid": paid})

        if paid and status == "succeeded":
            await self._activate_if_needed(db, last.payment_id, info)
            return "Оплата подтверждена ✅ Доступ активирован. Можешь писать: /ask <вопрос>"

        if status == "canceled":
            return "Платёж отменён. Можешь попробовать снова: /buy"

        return f"Платёж пока не подтверждён. Текущий статус: {status}. Попробуй чуть позже."

    async def on_status_update(self, payment_id: str, status: str, session: AsyncSession) -> None:
        p = await self._pay_svc.get_payment_by_id(session, payment_id)
        if not p:
            return
        await self._pay_svc.update_payment_status(session, payment_id, status)

    async def on_succeeded(self, payment_id: str, info: dict, session: AsyncSession) -> None:
        await self._activate_if_needed(session, payment_id, info)

    async def _activate_if_needed(self, db: AsyncSession, payment_id: str, info: dict) -> None:
        p = await self._pay_svc.get_payment_by_id(db, payment_id)
        if not p:
            return

        if info.get("status") != "succeeded":
            return

        await self._pay_svc.update_payment_status(db, payment_id, "succeeded")

        premium_until = await self._user_svc.activate_subscription(db, p.tg_id, self._settings.subscription_days)

        try:
            await self._bot.send_message(
                chat_id=p.tg_id,
                text=f"Оплата подтверждена ✅ Доступ активирован до {premium_until.strftime('%Y-%m-%d %H:%M:%S')} (UTC)\n\nПиши: /ask <вопрос>",
            )
        except Exception:
            logger.exception("Failed to send success message to user %s", p.tg_id)

        self._sheets.log_event(
            p.tg_id,
            "",
            "payment_succeeded",
            {"payment_id": payment_id, "premium_until": premium_until.strftime("%Y-%m-%d %H:%M:%S")},
        )
