from __future__ import annotations

import io
import logging
import os
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from .analysis import analyze_one, attach_prediction
from .storage import dashboard_data, persist_analyses

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("review_integrity")
MAX_BATCH_ROWS = int(os.getenv("MAX_BATCH_ROWS", "1000"))
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", "5000000"))
_configured_model_path = Path(os.getenv("MODEL_PATH", "artifacts/review_model.joblib"))
MODEL_PATH = (_configured_model_path if _configured_model_path.is_absolute()
              else Path(__file__).resolve().parents[1] / _configured_model_path)


def load_model() -> tuple[Any | None, dict[str, Any], str | None]:
    if not MODEL_PATH.exists():
        logger.warning("No trained review model found at %s", MODEL_PATH)
        return None, {}, None
    try:
        artifact = joblib.load(MODEL_PATH)
        model = artifact.get("pipeline", artifact) if isinstance(artifact, dict) else artifact
        metadata = artifact.get("metadata", {}) if isinstance(artifact, dict) else {}
        if not hasattr(model, "predict_proba") or not hasattr(model, "classes_"):
            raise ValueError("artifact must provide predict_proba and classes_")
        if 1 not in list(model.classes_):
            raise ValueError("artifact classes_ must contain suspicious label 1")
        return model, metadata, None
    except Exception as exc:
        logger.exception("Could not load review model from %s", MODEL_PATH)
        return None, {}, str(exc)


MODEL, MODEL_METADATA, MODEL_LOAD_ERROR = load_model()


def model_status() -> str:
    if MODEL is None:
        return "load_error" if MODEL_LOAD_ERROR else "not_trained"
    return "demo" if MODEL_METADATA.get("model_type") == "synthetic_demo" else "ready"
app = FastAPI(title="Review Integrity API", version="0.1.0")
origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"],
                   allow_headers=["Content-Type", "Authorization"])


class ReviewInput(BaseModel):
    review_text: str = Field(min_length=3, max_length=10000)
    product_id: str | None = Field(default=None, max_length=200)
    reviewer_id: str | None = Field(default=None, max_length=200)
    rating: float | None = Field(default=None, ge=1, le=5)
    review_date: date | None = None

    @field_validator("review_text")
    @classmethod
    def review_text_must_contain_content(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("review_text must contain at least 3 non-whitespace characters")
        return value


@app.get("/health")
def health() -> dict[str, str]:
    status = model_status()
    return {"status": "ok", "model_status": status, "model_path": str(MODEL_PATH),
            **({"model_error": MODEL_LOAD_ERROR} if MODEL_LOAD_ERROR else {})}


@app.post("/api/v1/analyze")
def analyze(payload: ReviewInput) -> dict[str, Any]:
    row = payload.model_dump(mode="json")
    result = attach_prediction(analyze_one(row), MODEL, model_status())
    result["_raw_text"] = row["review_text"]
    try:
        result["persistence_status"] = "saved" if persist_analyses([result]) else "not_configured"
    except Exception:
        logger.exception("Could not persist single review analysis")
        result["persistence_status"] = "failed"
    result.pop("_raw_text", None)
    return result


@app.post("/api/v1/analyze/batch")
async def analyze_batch(file: UploadFile = File(...)) -> dict[str, Any]:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(415, "Upload a .csv file")
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "CSV exceeds the 5 MB upload limit")
    try:
        frame = pd.read_csv(io.BytesIO(raw))
    except Exception as exc:
        raise HTTPException(400, "Could not parse CSV") from exc
    if "review_text" not in frame.columns:
        raise HTTPException(422, "CSV must contain a review_text column")
    if len(frame) > MAX_BATCH_ROWS:
        raise HTTPException(413, f"CSV exceeds the {MAX_BATCH_ROWS} row limit")
    normalized_text = frame.review_text.astype(str).str.strip()
    if frame.review_text.isna().any() or (normalized_text.str.len() < 3).any() or (normalized_text.str.len() > 10000).any():
        raise HTTPException(422, "Review text must contain 3–10,000 non-whitespace characters")
    frame["review_text"] = normalized_text
    for field in ("rating",):
        if field in frame:
            frame[field] = pd.to_numeric(frame[field], errors="coerce")
            if ((frame[field].dropna() < 1) | (frame[field].dropna() > 5)).any():
                raise HTTPException(422, "Ratings must be between 1 and 5")
    records = frame.to_dict(orient="records")
    parsed_dates = [None] * len(records)
    if "review_date" in frame:
        parsed = pd.to_datetime(frame["review_date"], errors="coerce", utc=True)
        invalid = frame["review_date"].notna() & parsed.isna()
        if invalid.any():
            raise HTTPException(422, "review_date contains an invalid date")
        parsed_dates = [value if pd.notna(value) else None for value in parsed]
    # For dated records, compute reviewer history only from strictly earlier dates.
    # Reviews sharing a calendar date have no reliable within-day order, so their
    # same-day count is explicitly a retrospective batch-cohort signal.
    day_cohorts: Counter = Counter()
    for row, parsed_date in zip(records, parsed_dates):
        rid = row.get("reviewer_id")
        if rid is not None and pd.notna(rid) and parsed_date is not None:
            day_cohorts[(str(rid), parsed_date.date().isoformat())] += 1
    processing_order = sorted(range(len(records)), key=lambda i: (parsed_dates[i] is None,
                                                                    parsed_dates[i] or pd.Timestamp.max.tz_localize("UTC"), i))
    seen_reviewer_dates: dict[str, Counter] = {}
    seen_texts: list[str] = []
    results: list[dict[str, Any] | None] = [None] * len(records)
    for index in processing_order:
        row = records[index]
        text = str(row["review_text"])
        rid = str(row.get("reviewer_id")) if pd.notna(row.get("reviewer_id")) else None
        parsed_date = parsed_dates[index]
        day = parsed_date.date().isoformat() if parsed_date is not None else None
        history = seen_reviewer_dates.get(rid, Counter()) if rid and parsed_date is not None else Counter()
        prior_n = sum(count for earlier_day, count in history.items() if earlier_day < day) if day else 0
        cohort_n = int(day_cohorts[(rid, day)]) if rid and day else 0
        result = attach_prediction(analyze_one(row, seen_texts, prior_n, cohort_n), MODEL, model_status())
        result["_raw_text"] = text
        result["review_date"] = row.get("review_date")
        results[index] = result
        seen_texts.append(text)
        if rid and day:
            seen_reviewer_dates.setdefault(rid, Counter())[day] += 1
    complete_results = [result for result in results if result is not None]
    persisted = False
    try:
        persisted = persist_analyses(complete_results)
    except Exception:
        logger.exception("Could not persist batch analysis")
        persisted = False
    for result in complete_results:
        result.pop("_raw_text", None)
    return {"total": len(complete_results), "model_status": model_status(),
            "persistence_status": "saved" if persisted else "not_configured_or_failed", "results": complete_results}


@app.get("/api/v1/dashboard")
def dashboard() -> dict[str, Any]:
    try:
        data = dashboard_data()
    except Exception as exc:
        raise HTTPException(503, "Configured dashboard storage is unavailable") from exc
    return data or {"total_reviews": 0, "suspicious_reviews": 0, "likely_genuine_reviews": 0,
                    "sentiment_distribution": {}, "source": "not_configured"}
