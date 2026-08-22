"""
Detection Service
------------------
Finds payments that need recovery attention and classifies each failure
as "soft" (worth retrying automatically) or "hard" (customer action needed,
e.g. update card) BEFORE we even call the AI. This keeps the AI call focused
on reasoning/messaging, not basic classification -- cheaper and more reliable.
"""
from sqlalchemy.orm import Session

from app.models.models import Payment, PaymentStatus, FailureReason

# Which failure reasons can plausibly be fixed by just retrying the charge,
# vs. reasons that need the customer to actually do something (update card).
SOFT_FAIL_REASONS = {
    FailureReason.INSUFFICIENT_FUNDS,   # balance might be topped up later
    FailureReason.BANK_DECLINED,         # could be a temporary bank-side block
    FailureReason.NETWORK_ERROR,          # pure infra glitch, safe to retry
}

HARD_FAIL_REASONS = {
    FailureReason.CARD_EXPIRED,   # retrying won't help, card is dead
    FailureReason.CARD_INVALID,    # retrying won't help, bad card details
}

MAX_RETRIES = 3


def get_failed_payments(db: Session):
    """All payments currently sitting in FAILED state."""
    return db.query(Payment).filter(Payment.status == PaymentStatus.FAILED).all()


def classify_failure(payment: Payment) -> str:
    """Returns 'soft', 'hard', or 'unknown' based on the failure reason."""
    if payment.failure_reason in SOFT_FAIL_REASONS:
        return "soft"
    if payment.failure_reason in HARD_FAIL_REASONS:
        return "hard"
    return "unknown"


def get_recovery_queue(db: Session):
    """
    Builds the list of payments the agent should act on right now, each
    tagged with its classification and whether it's still eligible for
    an automatic retry (vs. already maxed out -> needs escalation).
    """
    failed_payments = get_failed_payments(db)
    queue = []
    for payment in failed_payments:
        classification = classify_failure(payment)
        eligible_for_retry = (
            classification == "soft" and payment.retry_count < MAX_RETRIES
        )
        queue.append({
            "payment": payment,
            "classification": classification,
            "eligible_for_retry": eligible_for_retry,
            "retries_used": payment.retry_count,
        })
    return queue
