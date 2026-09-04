from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pathlib import Path

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


@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok", "service": "AI Revenue Recovery Agent"}
