"""
main.py

FastAPI application exposing the Tasdeeq claim-verification pipeline as a web API.
"""

import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from Backend.pipeline import TasdeeqPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Tasdeeq API",
    description="Roman Urdu misinformation verification pipeline",
    version="1.0.0",
)

# Allow requests from any frontend (browser, Streamlit, etc.).
# In a production deployment with a known frontend domain, replace
# allow_origins=["*"] with the specific domain(s) for better security.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# The pipeline is created once when the server starts, not on every request --
# this avoids re-initializing API clients unnecessarily.
pipeline = TasdeeqPipeline()

MAX_CLAIM_LENGTH = 2000  # Reasonable upper bound to prevent abuse/oversized requests.


class VerifyRequest(BaseModel):
    """Request body shape for the /verify endpoint."""
    claim: str

class ReasoningTranslations(BaseModel):
    english: str
    roman_urdu: str | None = None
    urdu_script: str | None = None

class VerifyResponse(BaseModel):
    """Response body shape for the /verify endpoint."""
    status: str
    original_text: str | None = None
    english_translation: str | None = None
    core_claim: str | None = None
    sources: list = []
    verdict: str | None = None
    confidence: str | None = None
    reasoning: ReasoningTranslations | None = None
    error_stage: str | None = None
    error_message: str | None = None


@app.get("/")
def root():
    """Simple health-check endpoint -- confirms the server is running."""
    return {"message": "Tasdeeq API is running."}


@app.post("/verify", response_model=VerifyResponse)
def verify_claim(request: VerifyRequest):
    """
    Accepts a raw claim (Roman Urdu, English, or mixed) and returns
    a verdict based on live web evidence.
    """
    claim_text = request.claim.strip() if request.claim else ""

    if not claim_text:
        raise HTTPException(status_code=400, detail="Claim text cannot be empty.")

    if len(claim_text) > MAX_CLAIM_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Claim text too long (max {MAX_CLAIM_LENGTH} characters).",
        )

    logger.info("Received verification request (length=%d chars).", len(claim_text))
    result = pipeline.verify(claim_text) or {}

    normalized_result = dict(result)
    normalized_result["status"] = "error" if normalized_result.get("is_error") else "ok"
    normalized_result.setdefault("sources", [])
    normalized_result.setdefault("error_stage", None)
    normalized_result.setdefault("error_message", None)

    return normalized_result

from fastapi.staticfiles import StaticFiles

app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")