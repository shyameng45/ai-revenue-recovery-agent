import enum
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Enum, Boolean, Text
)
from sqlalchemy.orm import relationship

from app.database import Base


class PaymentStatus(str, enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"
    RECOVERED = "recovered"
    ABANDONED = "abandoned"  # gave up after max retries


class FailureReason(str, enum.Enum):
    INSUFFICIENT_FUNDS = "insufficient_funds"   # soft fail -> retry later works
    CARD_EXPIRED = "card_expired"                 # hard fail -> need new card
    BANK_DECLINED = "bank_declined"                # soft fail -> retry might work
    NETWORK_ERROR = "network_error"                # soft fail -> retry immediately
    CARD_INVALID = "card_invalid"                   # hard fail -> need new card
    UNKNOWN = "unknown"


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    preferred_language = Column(String, default="hinglish")

    subscriptions = relationship("Subscription", back_populates="customer")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    plan_name = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    billing_cycle = Column(String, default="monthly")  # monthly / yearly
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("Customer", back_populates="subscriptions")
    payments = relationship("Payment", back_populates="subscription")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(Enum(PaymentStatus), default=PaymentStatus.FAILED)
    failure_reason = Column(Enum(FailureReason), nullable=True)
    attempted_at = Column(DateTime, default=datetime.utcnow)
    diagnosis_note = Column(Text, nullable=True)  # AI's reasoning for why it failed
    retry_count = Column(Integer, default=0)

    subscription = relationship("Subscription", back_populates="payments")
    recovery_attempts = relationship("RecoveryAttempt", back_populates="payment")


class RecoveryAttempt(Base):
    __tablename__ = "recovery_attempts"

    id = Column(Integer, primary_key=True, index=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=False)
    action_type = Column(String, nullable=False)  # "retry" or "message" or "escalate"
    message_sent = Column(Text, nullable=True)     # the Hinglish message generated
    outcome = Column(String, nullable=True)         # "success" / "failed" / "pending"
    created_at = Column(DateTime, default=datetime.utcnow)

    payment = relationship("Payment", back_populates="recovery_attempts")
