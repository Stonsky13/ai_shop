from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def buy_keyboard(pay_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Оплатить", url=pay_url)],
            [InlineKeyboardButton(text="Проверить оплату", callback_data="check_payment")],
        ]
    )


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Купить доступ", callback_data="buy")],
            [InlineKeyboardButton(text="Статус", callback_data="status")],
        ]
    )
