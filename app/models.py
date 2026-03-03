from __future__ import annotations

from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, String, DateTime, Float, Index

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    username: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    premium_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow, nullable=False)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    payment_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    tg_id: Mapped[int] = mapped_column(Integer, index=True)

    amount_rub: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)  # pending/succeeded/canceled/waiting_for_capture...
    confirmation_url: Mapped[str] = mapped_column(String(2048), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow, nullable=False)


Index("ix_payments_tg_id_created_at", Payment.tg_id, Payment.created_at)
