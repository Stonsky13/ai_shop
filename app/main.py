from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import load_settings, Settings
from app.logging_setup import setup_logging
from app.middlewares.middleware import DbSessionMiddleware
from app.handlers.handlers import router
from app.clients.yookassa_client import YooKassaClient
from app.clients.ai_client import AiClient
from app.clients.sheets_client import SheetsClient
from app.services.services import UserService, PaymentService, PaymentPoller
from app.database.db import create_engine, create_sessionmaker, init_models
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


class AiFlow:
    def __init__(self, ai: AiClient, sheets: SheetsClient) -> None:
        self._ai = ai
        self._sheets = sheets

    async def ask_and_log(self, tg_id: int, username: str, question: str) -> str:
        self._sheets.log_event(tg_id, username, "ai_ask", {"q": question})
        try:
            ans = await self._ai.ask(question)
            self._sheets.log_event(tg_id, username, "ai_answer", {"len": len(ans)})
            return ans
        except Exception as e:
            logger.exception("AI request failed")
            self._sheets.log_event(tg_id, username, "ai_answer_error", {"error": str(e)})
            return "Ошибка при обращении к AI. Попробуй позже."


async def main() -> None:
    settings = load_settings()
    setup_logging(settings.log_level)

    engine = create_engine(settings.database_url)
    sessionmaker = create_sessionmaker(engine)

    await init_models(engine)

    bot = Bot(
        token=settings.tg_bot_token,
    )
    dp = Dispatcher()
    dp.message.middleware(DbSessionMiddleware(sessionmaker))
    dp.callback_query.middleware(DbSessionMiddleware(sessionmaker))

    yk = YooKassaClient(settings.yookassa_shop_id, settings.yookassa_secret_key, settings.yookassa_return_url)
    ai = AiClient(settings.ai_base_url, settings.ai_api_key, settings.ai_model)
    sheets = SheetsClient(settings.gcp_service_account_json, settings.sheets_spreadsheet_id, settings.sheets_sheet_name)

    user_svc = UserService()
    pay_svc = PaymentService()

    pay_flow_placeholder = {"obj": None}

    poller = PaymentPoller(
        attempts=settings.payment_poll_attempts,
        interval_sec=settings.payment_poll_interval_sec,
        yookassa_get_status_fn=yk.get_payment,
        on_succeeded_async_fn=lambda payment_id, info, session: pay_flow_placeholder["obj"].on_succeeded(payment_id, info, session),
        on_status_update_async_fn=lambda payment_id, status, session: pay_flow_placeholder["obj"].on_status_update(payment_id, status, session),
        sessionmaker=sessionmaker,
    )

    pay_flow = PaymentFlow(settings, yk, sheets, user_svc, pay_svc, bot, poller)
    pay_flow_placeholder["obj"] = pay_flow

    ai_flow = AiFlow(ai, sheets)

    dp["user_svc"] = user_svc
    dp["pay_flow"] = pay_flow
    dp["ai_flow"] = ai_flow

    dp.include_router(router)

    logger.info("Bot starting with long polling...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, user_svc=user_svc, pay_flow=pay_flow, ai_flow=ai_flow)


if __name__ == "__main__":
    asyncio.run(main())
