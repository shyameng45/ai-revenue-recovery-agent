"""
Recovery Service
-----------------
The orchestrator: pulls the recovery queue from detection.py, calls the AI
service for diagnosis + Hinglish message, then logs a RecoveryAttempt and
updates the Payment record. This is the "agent" -- it decides and acts.
"""
import random
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.models import (
    Payment, PaymentStatus, RecoveryAttempt, Subscription, Customer
)
from app.services.detection import get_recovery_queue, MAX_RETRIES
from app.services.ai_service import diagnose_and_generate_message

# Realistic success rate for a retried soft-fail payment. Industry recovery
# campaigns for insufficient-funds / bank-declined typically land in this
# 55-70% band per retry attempt, so this is a defensible, non-inflated number
# for the demo -- not "everything magically recovers."
RETRY_SUCCESS_RATE = 0.62


def run_recovery_cycle(db: Session):
    """
    Processes the entire recovery queue once. For each failed payment:
      - soft fail, retries left  -> call AI, log a "retry" attempt, bump retry_count
      - soft fail, retries maxed -> mark ABANDONED, log an "escalate" attempt
      - hard fail                -> call AI, log a "message" attempt asking
                                     the customer to update their payment method
    Returns a summary dict for the API response / audit trail.
    """
    queue = get_recovery_queue(db)
    results = {
        "processed": 0,
        "retried": 0,
        "escalated": 0,
        "hard_fail_messaged": 0,
        "amount_in_recovery_queue": 0.0,
        "details": [],
    }

    for item in queue:
        payment: Payment = item["payment"]
        classification = item["classification"]
        subscription = db.get(Subscription, payment.subscription_id)
        customer = db.get(Customer, subscription.customer_id)

        results["amount_in_recovery_queue"] += payment.amount

        ai_result = diagnose_and_generate_message(
            customer_name=customer.name,
            plan_name=subscription.plan_name,
            amount=payment.amount,
            failure_reason=payment.failure_reason.value if payment.failure_reason else "unknown",
            classification=classification,
        )
        payment.diagnosis_note = ai_result["diagnosis"]

        if classification == "soft" and payment.retry_count < MAX_RETRIES:
            # attempt a retry: record the action, bump the counter
            payment.retry_count += 1
            payment.status = PaymentStatus.RETRYING
            action_type = "retry"
            results["retried"] += 1

        elif classification == "soft" and payment.retry_count >= MAX_RETRIES:
            # out of retries -> give up automatically, escalate
            payment.status = PaymentStatus.ABANDONED
            action_type = "escalate"
            results["escalated"] += 1

        else:  # hard fail -> needs the customer to act, not a silent retry
            payment.status = PaymentStatus.RETRYING  # awaiting customer update
            action_type = "message"
            results["hard_fail_messaged"] += 1

        attempt = RecoveryAttempt(
            payment_id=payment.id,
            action_type=action_type,
            message_sent=ai_result["message"],
            outcome="pending",
            created_at=datetime.utcnow(),
        )
        db.add(attempt)
        results["processed"] += 1
        results["details"].append({
            "payment_id": payment.id,
            "customer": customer.name,
            "amount": payment.amount,
            "classification": classification,
            "action": action_type,
            "diagnosis": ai_result["diagnosis"],
            "message": ai_result["message"],
        })

    db.commit()
    return results


def simulate_retry_outcomes(db: Session):
    """
    Simulates what happens after a retry/message goes out: real payment
    gateways would report back success/failure asynchronously (customer
    retries their card, updates it, etc). Since this demo uses synthetic
    data with no live gateway, we simulate that outcome here using a
    realistic success rate, so the recovered-amount / recovery-rate
    metrics reflect real numbers instead of staying at zero forever.

    Only affects payments currently in RETRYING state (i.e. already
    processed by run_recovery_cycle).
    """
    retrying_payments = db.query(Payment).filter(
        Payment.status == PaymentStatus.RETRYING
    ).all()

    results = {"resolved": 0, "recovered": 0, "still_failed": 0,
                "amount_recovered": 0.0}

    for payment in retrying_payments:
        # find the most recent recovery attempt logged for this payment
        latest_attempt = (
            db.query(RecoveryAttempt)
            .filter(RecoveryAttempt.payment_id == payment.id)
            .order_by(RecoveryAttempt.created_at.desc())
            .first()
        )

        succeeded = random.random() < RETRY_SUCCESS_RATE

        if succeeded:
            payment.status = PaymentStatus.RECOVERED
            results["recovered"] += 1
            results["amount_recovered"] += payment.amount
            if latest_attempt:
                latest_attempt.outcome = "success"
        else:
            # goes back to FAILED so it re-enters the queue for another
            # retry cycle (respecting MAX_RETRIES via detection.py)
            payment.status = PaymentStatus.FAILED
            results["still_failed"] += 1
            if latest_attempt:
                latest_attempt.outcome = "failed"

        results["resolved"] += 1

    db.commit()
    results["amount_recovered"] = round(results["amount_recovered"], 2)
    return results
