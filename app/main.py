from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from app.config import load_settings
from app.logging_setup import setup_logging
from app.middlewares.middleware import DbSessionMiddleware
from app.handlers.handlers import router
from app.clients.yookassa_client import YooKassaClient
from app.clients.ai_client import AiClient
from app.clients.sheets_client import SheetsClient
from app.services.services import UserService, PaymentService, PaymentPoller
from app.database.db import create_engine, create_sessionmaker, init_models
from app.flows.payment_flow import PaymentFlow
from app.flows.ai_flow import AiFlow

logger = logging.getLogger(__name__)



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


    poller = PaymentPoller(
        attempts=settings.payment_poll_attempts,
        interval_sec=settings.payment_poll_interval_sec,
        yookassa_get_status_fn=yk.get_payment,
        sessionmaker=sessionmaker,
    )

    pay_flow = PaymentFlow(settings, yk, sheets, user_svc, pay_svc, bot, poller)
    poller.set_callbacks(
        on_succeeded=pay_flow.on_succeeded,
        on_status_update=pay_flow.on_status_update
    )
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
