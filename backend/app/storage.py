"""Optional Supabase persistence. The service key is read server-side only."""
import os
from typing import Any


def _client() -> Any | None:
    url, key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return None
    from supabase import create_client
    return create_client(url, key)


def persist_analyses(results: list[dict[str, Any]]) -> bool:
    client = _client()
    if client is None:
        return False
    review_rows = [{k: value for k, value in {
        "source_review_id": r.get("review_id"), "product_id": r.get("product_id"),
        "reviewer_id": r.get("reviewer_id"), "review_text": r.get("_raw_text", ""),
        "rating": r.get("rating"), "review_date": r.get("review_date"),
    }.items() if value is not None} for r in results]
    inserted = client.table("reviews").insert(review_rows).execute().data
    analysis_rows = []
    for review, result in zip(inserted, results):
        analysis_rows.append({"review_id": review["id"], "prediction": result["prediction"],
                              "risk_score": result["risk_score"],
                              "sentiment": result["sentiment"]["label"],
                              "signals": result["signals"]})
    if analysis_rows:
        client.table("analyses").insert(analysis_rows).execute()
    return True


def dashboard_data() -> dict[str, Any] | None:
    client = _client()
    if client is None:
        return None
    rows = client.table("analyses").select("prediction,sentiment").execute().data
    predictions: dict[str, int] = {}
    sentiments: dict[str, int] = {}
    for row in rows:
        predictions[row["prediction"]] = predictions.get(row["prediction"], 0) + 1
        sentiments[row["sentiment"]] = sentiments.get(row["sentiment"], 0) + 1
    return {"total_reviews": len(rows),
            "suspicious_reviews": predictions.get("potentially_suspicious", 0) + predictions.get("likely_fake", 0),
            "likely_genuine_reviews": predictions.get("likely_genuine", 0),
            "sentiment_distribution": sentiments, "source": "supabase"}
