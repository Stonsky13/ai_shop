from __future__ import annotations

from datetime import datetime, timedelta


def utcnow_naive() -> datetime:
    return datetime.utcnow()


def add_days(dt: datetime, days: int) -> datetime:
    return (dt + timedelta(days=days))


def is_premium_active(premium_until: datetime | None) -> bool:
    if premium_until is None:
        return False
    return premium_until > utcnow_naive()
