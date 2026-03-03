from __future__ import annotations

import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.keyboards import buy_keyboard, main_menu_keyboard
from app.services.services import UserService
from app.utils.utils import is_premium_active
from app.database.models import User
from sqlalchemy import select


logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("start"))
async def cmd_start(msg: Message) -> None:
    text = (
        "Привет! Я бот с оплатой через ЮKassa, AI через ProxyAPI и логированием в Google Sheets.\n\n"
        "Команды:\n"
        "/buy — купить доступ на 30 дней\n"
        "/status — проверить доступ\n"
        "/ask <вопрос> — задать вопрос (нужен активный доступ)\n"
    )
    await msg.answer(text, reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "status")
async def cb_status(cb: CallbackQuery, db: AsyncSession, user_svc: UserService) -> None:
    tg_id = cb.from_user.id
    text = await user_svc.get_status_text(db, tg_id)
    await cb.message.answer(text)
    await cb.answer()


@router.message(Command("status"))
async def cmd_status(msg: Message, db: AsyncSession, user_svc: UserService) -> None:
    text = await user_svc.get_status_text(db, msg.from_user.id)
    await msg.answer(text)


@router.callback_query(F.data == "buy")
async def cb_buy(cb: CallbackQuery, db: AsyncSession, user_svc: UserService, pay_flow) -> None:
    await cb.answer()
    await _buy_impl(
        chat_id=cb.message.chat.id,
        tg_id=cb.from_user.id,
        username=cb.from_user.username or "",
        db=db,
        user_svc=user_svc,
        pay_flow=pay_flow,
        send_fn=cb.message.answer,
    )


@router.message(Command("buy"))
async def cmd_buy(msg: Message, db: AsyncSession, user_svc: UserService, pay_flow) -> None:
    await _buy_impl(
        chat_id=msg.chat.id,
        tg_id=msg.from_user.id,
        username=msg.from_user.username or "",
        db=db,
        user_svc=user_svc,
        pay_flow=pay_flow,
        send_fn=msg.answer,
    )


async def _buy_impl(chat_id: int, tg_id: int, username: str, db: AsyncSession, user_svc: UserService, pay_flow, send_fn):
    await user_svc.get_or_create_user(db, tg_id, username)

    pay_url = await pay_flow.create_and_start_polling(db, tg_id, username, chat_id=chat_id)
    await send_fn(
        "Открой ссылку для оплаты. После оплаты нажми “Проверить оплату” или подожди пару минут — я попробую подтвердить сам.",
        reply_markup=buy_keyboard(pay_url),
    )


@router.callback_query(F.data == "check_payment")
async def cb_check_payment(cb: CallbackQuery, db: AsyncSession, pay_flow) -> None:
    await cb.answer()
    tg_id = cb.from_user.id
    res = await pay_flow.check_last_payment(db, tg_id, cb.from_user.username or "", chat_id=cb.message.chat.id)
    await cb.message.answer(res)


@router.message(Command("ask"))
async def cmd_ask(msg: Message, db: AsyncSession, ai_flow) -> None:
    text = (msg.text or "").strip()
    parts = text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await msg.answer("Использование: /ask <вопрос>")
        return

    q = await db.execute(select(User).where(User.tg_id == msg.from_user.id))
    user = q.scalar_one_or_none()

    if not user or not is_premium_active(user.premium_until):
        await msg.answer("Доступ не активен. Купи подписку: /buy")
        return

    question = parts[1].strip()
    answer = await ai_flow.ask_and_log(
        tg_id=msg.from_user.id,
        username=msg.from_user.username or "",
        question=question,
    )
    await msg.answer(answer)
