from __future__ import annotations

from dataclasses import dataclass
import os


def _must(name: str) -> str:
    v = (os.getenv(name) or "").strip()
    if not v:
        raise RuntimeError(f"Missing required env var: {name}")
    return v


@dataclass(frozen=True)
class Settings:
    tg_bot_token: str

    yookassa_shop_id: str
    yookassa_secret_key: str
    yookassa_return_url: str

    subscription_days: int
    subscription_price_rub: float

    ai_base_url: str
    ai_api_key: str
    ai_model: str

    gcp_service_account_json: str
    sheets_spreadsheet_id: str
    sheets_sheet_name: str

    database_url: str

    payment_poll_attempts: int
    payment_poll_interval_sec: int

    log_level: str


def load_settings() -> Settings:
    return Settings(
        tg_bot_token=_must("TG_BOT_TOKEN"),

        yookassa_shop_id=_must("YOOKASSA_SHOP_ID"),
        yookassa_secret_key=_must("YOOKASSA_SECRET_KEY"),
        yookassa_return_url=_must("YOOKASSA_RETURN_URL"),

        subscription_days=int((os.getenv("SUBSCRIPTION_DAYS") or "30").strip()),
        subscription_price_rub=float((os.getenv("SUBSCRIPTION_PRICE_RUB") or "199.00").strip()),

        ai_base_url=_must("AI_BASE_URL"),
        ai_api_key=_must("AI_API_KEY"),
        ai_model=(os.getenv("AI_MODEL") or "gpt-4o-mini").strip(),

        gcp_service_account_json=_must("GCP_SERVICE_ACCOUNT_JSON"),
        sheets_spreadsheet_id=_must("SHEETS_SPREADSHEET_ID"),
        sheets_sheet_name=(os.getenv("SHEETS_SHEET_NAME") or "Sheet1").strip(),

        database_url=(os.getenv("DATABASE_URL") or "./data/app.db").strip(),

        payment_poll_attempts=int((os.getenv("PAYMENT_POLL_ATTEMPTS") or "24").strip()),
        payment_poll_interval_sec=int((os.getenv("PAYMENT_POLL_INTERVAL_SEC") or "5").strip()),

        log_level=(os.getenv("LOG_LEVEL") or "INFO").strip(),
    )