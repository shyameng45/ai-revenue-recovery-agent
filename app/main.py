from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers import recovery_router

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AI Revenue Recovery Agent",
    description=(
        "Detects failed subscription payments, diagnoses why they failed, "
        "and takes recovery action (smart retries + Hinglish reminder messages)."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(recovery_router.router, prefix="/api", tags=["recovery"])


@app.get("/")
def root():
    return {
        "message": "AI Revenue Recovery Agent is running.",
        "docs": "/docs",
        "endpoints": {
            "recovery_queue": "GET /api/queue",
            "run_recovery": "POST /api/recover",
            "metrics": "GET /api/metrics",
            "audit_trail": "GET /api/audit-trail",
            "all_payments": "GET /api/payments",
        },
    }
