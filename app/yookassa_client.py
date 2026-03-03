from __future__ import annotations

import logging
from typing import Any

from yookassa import Configuration, Payment as YooPayment
from yookassa.domain.common.confirmation_type import ConfirmationType
from yookassa.domain.request.payment_request_builder import PaymentRequestBuilder
from yookassa.domain.models.currency import Currency


logger = logging.getLogger(__name__)


class YooKassaClient:
    def __init__(self, shop_id: str, secret_key: str, return_url: str) -> None:
        self._return_url = return_url
        Configuration.configure(shop_id, secret_key)

    def create_payment(self, amount_rub: float, description: str, tg_id: int, username: str) -> dict[str, Any]:
        builder = PaymentRequestBuilder()
        request = (
            builder
            .set_amount({"value": f"{amount_rub:.2f}", "currency": Currency.RUB})
            .set_confirmation({"type": ConfirmationType.REDIRECT, "return_url": self._return_url})
            .set_capture(True)
            .set_description(description)
            .set_metadata({"tg_id": str(tg_id), "username": username or ""})
            .build()
        )

        res = YooPayment.create(request)

        payment_id = getattr(res, "id", "") or ""
        status = getattr(res, "status", "") or ""
        confirmation_url = ""
        confirmation = getattr(res, "confirmation", None)
        if confirmation is not None:
            confirmation_url = getattr(confirmation, "confirmation_url", "") or ""

        if not payment_id or not confirmation_url:
            logger.error("YooKassa create_payment unexpected response: %s", res)
            raise RuntimeError("YooKassa не вернула payment_id/confirmation_url")

        return {
            "payment_id": payment_id,
            "status": status,
            "confirmation_url": confirmation_url,
        }

    def get_payment(self, payment_id: str) -> dict[str, Any]:
        res = YooPayment.find_one(payment_id)
        status = getattr(res, "status", "") or ""
        paid = bool(getattr(res, "paid", False))
        amount = getattr(res, "amount", None)

        amount_value = None
        amount_currency = None
        if amount is not None:
            amount_value = getattr(amount, "value", None)
            amount_currency = getattr(amount, "currency", None)

        metadata = getattr(res, "metadata", None)
        md = {}
        if metadata is not None:
            # metadata может быть dict-like
            try:
                md = dict(metadata)
            except Exception:
                md = {}

        return {
            "payment_id": getattr(res, "id", payment_id),
            "status": status,
            "paid": paid,
            "amount_value": amount_value,
            "amount_currency": amount_currency,
            "metadata": md,
        }
