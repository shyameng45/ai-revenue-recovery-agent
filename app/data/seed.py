"""
Generates synthetic data: customers, subscriptions, and a batch of payments
(mix of success + realistic failures) so the recovery agent has something
to work on.

Run with: ./venv/bin/python -m app.data.seed
"""
import random
from datetime import datetime, timedelta

from app.database import SessionLocal, Base, engine
from app.models.models import Customer, Subscription, Payment, PaymentStatus, FailureReason

Base.metadata.create_all(bind=engine)

FIRST_NAMES = ["Rahul", "Priya", "Amit", "Sneha", "Vikram", "Anjali", "Rohan",
               "Neha", "Karan", "Pooja", "Arjun", "Divya", "Suresh", "Kavya"]
LAST_NAMES = ["Sharma", "Verma", "Gupta", "Singh", "Reddy", "Iyer", "Mehta",
              "Joshi", "Kapoor", "Nair"]

PLANS = [
    ("Basic Monthly", 299.0, "monthly"),
    ("Pro Monthly", 799.0, "monthly"),
    ("Pro Yearly", 7999.0, "yearly"),
    ("Enterprise Monthly", 1999.0, "monthly"),
]

# Weighted so failures feel realistic (soft fails more common than hard fails)
FAILURE_WEIGHTS = [
    (FailureReason.INSUFFICIENT_FUNDS, 0.35),
    (FailureReason.BANK_DECLINED, 0.25),
    (FailureReason.NETWORK_ERROR, 0.15),
    (FailureReason.CARD_EXPIRED, 0.15),
    (FailureReason.CARD_INVALID, 0.10),
]


def weighted_failure_reason():
    reasons, weights = zip(*FAILURE_WEIGHTS)
    return random.choices(reasons, weights=weights, k=1)[0]


def seed(num_customers: int = 40, failure_rate: float = 0.35):
    db = SessionLocal()
    try:
        # wipe existing data for a clean seed
        db.query(Payment).delete()
        db.query(Subscription).delete()
        db.query(Customer).delete()
        db.commit()

        customers = []
        for i in range(num_customers):
            first = random.choice(FIRST_NAMES)
            last = random.choice(LAST_NAMES)
            customer = Customer(
                name=f"{first} {last}",
                email=f"{first.lower()}.{last.lower()}{i}@example.com",
                phone=f"9{random.randint(100000000, 999999999)}",
                preferred_language="hinglish",
            )
            db.add(customer)
            customers.append(customer)
        db.commit()

        payments_created = 0
        for customer in customers:
            plan_name, amount, cycle = random.choice(PLANS)
            sub = Subscription(
                customer_id=customer.id,
                plan_name=plan_name,
                amount=amount,
                billing_cycle=cycle,
                is_active=True,
                created_at=datetime.utcnow() - timedelta(days=random.randint(30, 365)),
            )
            db.add(sub)
            db.commit()

            # each customer gets 1-3 payment attempts in the current billing period
            is_failed = random.random() < failure_rate
            if is_failed:
                payment = Payment(
                    subscription_id=sub.id,
                    amount=amount,
                    status=PaymentStatus.FAILED,
                    failure_reason=weighted_failure_reason(),
                    attempted_at=datetime.utcnow() - timedelta(
                        hours=random.randint(1, 72)
                    ),
                    retry_count=0,
                )
            else:
                payment = Payment(
                    subscription_id=sub.id,
                    amount=amount,
                    status=PaymentStatus.SUCCESS,
                    failure_reason=None,
                    attempted_at=datetime.utcnow() - timedelta(
                        hours=random.randint(1, 72)
                    ),
                )
            db.add(payment)
            payments_created += 1

        db.commit()
        print(f"Seeded {len(customers)} customers, {payments_created} payments "
              f"({sum(1 for c in customers if True)} subscriptions).")

        failed = db.query(Payment).filter(Payment.status == PaymentStatus.FAILED).count()
        success = db.query(Payment).filter(Payment.status == PaymentStatus.SUCCESS).count()
        print(f"  -> {failed} failed, {success} success")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
