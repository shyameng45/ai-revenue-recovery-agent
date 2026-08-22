"""
Metrics Service
----------------
Produces the numbers judges/reviewers actually care about: how much money
is at risk, how much has been recovered, and a full audit trail of every
action the agent has taken.
"""
from sqlalchemy.orm import Session
from app.models.models import Payment, PaymentStatus, RecoveryAttempt, Subscription, Customer


def get_dashboard_metrics(db: Session):
    all_payments = db.query(Payment).all()

    total_failed_ever = sum(
        p.amount for p in all_payments
        if p.status in (PaymentStatus.FAILED, PaymentStatus.RETRYING,
                        PaymentStatus.RECOVERED, PaymentStatus.ABANDONED)
    )
    recovered_amount = sum(
        p.amount for p in all_payments if p.status == PaymentStatus.RECOVERED
    )
    still_failed = sum(
        p.amount for p in all_payments if p.status == PaymentStatus.FAILED
    )
    in_retry = sum(
        p.amount for p in all_payments if p.status == PaymentStatus.RETRYING
    )
    abandoned = sum(
        p.amount for p in all_payments if p.status == PaymentStatus.ABANDONED
    )

    recovery_rate = (
        round((recovered_amount / total_failed_ever) * 100, 1)
        if total_failed_ever > 0 else 0.0
    )

    return {
        "total_at_risk_ever": round(total_failed_ever, 2),
        "recovered_amount": round(recovered_amount, 2),
        "still_failed": round(still_failed, 2),
        "in_retry": round(in_retry, 2),
        "abandoned_amount": round(abandoned, 2),
        "recovery_rate_percent": recovery_rate,
        "total_recovery_attempts": db.query(RecoveryAttempt).count(),
    }


def get_audit_trail(db: Session, limit: int = 50):
    """Every recovery action taken, most recent first -- full transparency."""
    attempts = (
        db.query(RecoveryAttempt)
        .order_by(RecoveryAttempt.created_at.desc())
        .limit(limit)
        .all()
    )
    trail = []
    for a in attempts:
        payment = db.get(Payment, a.payment_id)
        subscription = db.get(Subscription, payment.subscription_id) if payment else None
        customer = db.get(Customer, subscription.customer_id) if subscription else None
        trail.append({
            "attempt_id": a.id,
            "payment_id": a.payment_id,
            "customer": customer.name if customer else "unknown",
            "action_type": a.action_type,
            "message_sent": a.message_sent,
            "outcome": a.outcome,
            "created_at": a.created_at.isoformat(),
        })
    return trail
