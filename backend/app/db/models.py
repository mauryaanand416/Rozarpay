from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    txn_ref: Mapped[str] = mapped_column(String(40), unique=True)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    customer_id: Mapped[str] = mapped_column(String(64), index=True)
    merchant_id: Mapped[str] = mapped_column(String(64), index=True)
    payment_method: Mapped[str] = mapped_column(String(24))
    device_id: Mapped[str] = mapped_column(String(64))
    ip_country: Mapped[str] = mapped_column(String(8))
    billing_country: Mapped[str] = mapped_column(String(8))
    cvv_match: Mapped[bool] = mapped_column(Boolean, default=True)
    avs_match: Mapped[bool] = mapped_column(Boolean, default=True)
    card_age_days: Mapped[int] = mapped_column(Integer, default=365)
    channel: Mapped[str] = mapped_column(String(24), default="web")
    is_fraud: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    def to_dict(self) -> dict:
        return {
            "txn_ref": self.txn_ref,
            "event_time": self.event_time.isoformat(),
            "amount": self.amount,
            "currency": self.currency,
            "customer_id": self.customer_id,
            "merchant_id": self.merchant_id,
            "payment_method": self.payment_method,
            "device_id": self.device_id,
            "ip_country": self.ip_country,
            "billing_country": self.billing_country,
            "cvv_match": self.cvv_match,
            "avs_match": self.avs_match,
            "card_age_days": self.card_age_days,
            "channel": self.channel,
        }


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    txn_ref: Mapped[str] = mapped_column(String(40), index=True)
    risk_score: Mapped[float] = mapped_column(Float)
    action: Mapped[str] = mapped_column(String(16), index=True)
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    features: Mapped[dict] = mapped_column(JSON, default=dict)
    model_version: Mapped[str] = mapped_column(String(32), default="none")
    threshold_used: Mapped[dict] = mapped_column(JSON, default=dict)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation_source: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditEntry(Base):
    __tablename__ = "audit_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    seq: Mapped[int] = mapped_column(Integer, unique=True)
    decision_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    actor: Mapped[str] = mapped_column(String(64))
    action_type: Mapped[str] = mapped_column(String(48))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    prev_hash: Mapped[str] = mapped_column(String(64))
    entry_hash: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    decision_id: Mapped[int] = mapped_column(Integer, index=True)
    txn_ref: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    analyst: Mapped[str] = mapped_column(String(64), default="analyst")
    outcome_label: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Digest(Base):
    __tablename__ = "digests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    content: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(16), default="llm")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


Index("ix_decisions_created", Decision.created_at)
