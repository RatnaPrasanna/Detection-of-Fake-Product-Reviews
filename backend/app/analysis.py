"""Transparent, deterministic review signal extraction."""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any

POSITIVE = {"excellent", "great", "love", "perfect", "wonderful", "amazing", "good", "best", "recommend", "happy", "quality", "easy"}
NEGATIVE = {"bad", "poor", "broken", "disappointing", "worst", "hate", "return", "waste", "terrible", "cheap", "defective", "unusable"}
PROMOTIONAL = {"buy now", "must buy", "life changing", "best product ever", "five stars", "100% recommend"}
WORD_RE = re.compile(r"[A-Za-z0-9']+")


def sentiment(text: str) -> dict[str, Any]:
    words = [w.lower() for w in WORD_RE.findall(text)]
    pos, neg = sum(w in POSITIVE for w in words), sum(w in NEGATIVE for w in words)
    total = pos + neg
    score = (pos - neg) / max(total, 1)
    label = "positive" if score > 0.15 else "negative" if score < -0.15 else "neutral"
    return {"label": label, "score": round(score, 3), "positive_terms": pos, "negative_terms": neg}


def text_features(text: str) -> dict[str, float | int]:
    words = WORD_RE.findall(text)
    lower = [w.lower() for w in words]
    sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
    return {
        "character_count": len(text), "word_count": len(words),
        "sentence_count": len(sentences),
        "uppercase_ratio": round(sum(c.isupper() for c in text) / max(sum(c.isalpha() for c in text), 1), 3),
        "exclamation_count": text.count("!"), "question_count": text.count("?"),
        "lexical_diversity": round(len(set(lower)) / max(len(lower), 1), 3),
        "repeated_word_count": sum(n - 1 for n in Counter(lower).values() if n > 1),
        "promotional_phrase_count": sum(text.lower().count(p) for p in PROMOTIONAL),
    }


def analyze_one(row: dict[str, Any], prior_texts: list[str] | None = None,
                reviewer_count: int = 0, burst_count: int = 0) -> dict[str, Any]:
    text = str(row.get("review_text") or "").strip()
    rating = row.get("rating")
    sent = sentiment(text)
    signals: list[str] = []
    mismatch = bool(rating is not None and ((float(rating) >= 4 and sent["label"] == "negative") or (float(rating) <= 2 and sent["label"] == "positive")))
    if mismatch:
        signals.append("Rating and text sentiment disagree")
    if text_features(text)["uppercase_ratio"] > 0.35 and len(text) > 20:
        signals.append("Unusually high capitalization")
    if text.count("!") >= 4:
        signals.append("Frequent exclamation marks")
    if any(phrase in text.lower() for phrase in PROMOTIONAL):
        signals.append("Promotional phrase detected")
    if reviewer_count >= 5:
        signals.append("Reviewer has at least five earlier reviews in the supplied history")
    if burst_count >= 3:
        signals.append("Several reviews from this reviewer occur on the same date")
    similarity = 0.0
    for previous in prior_texts or []:
        similarity = max(similarity, SequenceMatcher(None, text.lower(), previous.lower()).ratio())
    if similarity >= 0.92:
        signals.append("Near duplicate text found in this batch")
    return {
        "review_id": row.get("review_id"), "product_id": row.get("product_id"),
        "reviewer_id": row.get("reviewer_id"), "rating": rating,
        "sentiment": sent, "features": text_features(text),
        "behavior": {"prior_reviews_by_reviewer": reviewer_count or None,
                     "same_day_reviews_by_reviewer_in_batch": burst_count or None,
                     "closest_text_similarity": round(similarity, 3)},
        "rating_sentiment_mismatch": mismatch,
        "signals": signals, "review_text": text,
    }


def attach_prediction(result: dict[str, Any], model: Any | None, status: str | None = None) -> dict[str, Any]:
    if model is None:
        result.update({"prediction": None, "risk_score": None,
                       "model_status": status or "not_trained"})
    else:
        # Model input is raw review text; fitted pipeline owns all transformations.
        probabilities = model.predict_proba([result["review_text"]])[0]
        positive_index = list(model.classes_).index(1)
        risk = float(probabilities[positive_index])
        result.update({"prediction": "potentially_suspicious" if risk >= 0.5 else "likely_genuine",
                       "risk_score": round(risk * 100, 1), "model_status": status or "ready"})
    result.pop("review_text", None)
    return result
