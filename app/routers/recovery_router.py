from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.detection import get_recovery_queue
from app.services.recovery import run_recovery_cycle, simulate_retry_outcomes
from app.services.metrics import get_dashboard_metrics, get_audit_trail
from app.models.models import Payment, Subscription, Customer
from app.data.seed import seed

router = APIRouter()

@router.get("/queue")
def view_recovery_queue(db: Session = Depends(get_db)):
    """Shows every failed payment currently waiting for recovery action."""
    queue = get_recovery_queue(db)
    return [
        {
            "payment_id": item["payment"].id,
            "amount": item["payment"].amount,
            "failure_reason": item["payment"].failure_reason.value,
            "classification": item["classification"],
            "eligible_for_retry": item["eligible_for_retry"],
            "retries_used": item["retries_used"],
        }
        for item in queue
    ]

@router.post("/recover")
def trigger_recovery_cycle(db: Session = Depends(get_db)):
    """
    The main agent trigger: runs detection -> AI diagnosis -> action ->
    logging for every payment currently in the failed queue.
    """
    return run_recovery_cycle(db)

@router.post("/simulate-outcomes")
def simulate_outcomes(db: Session = Depends(get_db)):
    """
    Simulates real-world results of the retries/messages just sent
    (a real payment gateway would report these back asynchronously).
    Moves RETRYING payments to RECOVERED or back to FAILED based on a
    realistic success rate, so /api/metrics shows real recovered numbers.
    """
    return simulate_retry_outcomes(db)

@router.post("/reset-demo")
def reset_demo():
    """Reset synthetic demo data so the recovery flow can be replayed."""
    seed()
    return {"status": "reset", "message": "Demo data reset successfully."}

@router.get("/metrics")
def view_metrics(db: Session = Depends(get_db)):
    """Dashboard numbers: money recovered, still at risk, recovery rate."""
    return get_dashboard_metrics(db)

@router.get("/audit-trail")
def view_audit_trail(limit: int = 50, db: Session = Depends(get_db)):
    """Full log of every action the agent has taken, most recent first."""
    return get_audit_trail(db, limit=limit)

@router.get("/payments")
def list_all_payments(db: Session = Depends(get_db)):
    """All payments in the system with their current status, for debugging/demo."""
    payments = db.query(Payment).all()
    result = []
    for p in payments:
        sub = db.get(Subscription, p.subscription_id)
        cust = db.get(Customer, sub.customer_id)
        result.append({
            "payment_id": p.id,
            "customer": cust.name,
            "plan": sub.plan_name,
            "amount": p.amount,
            "status": p.status.value,
            "failure_reason": p.failure_reason.value if p.failure_reason else None,
            "retry_count": p.retry_count,
            "diagnosis_note": p.diagnosis_note,
        })
    return result
