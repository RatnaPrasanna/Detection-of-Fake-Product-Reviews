from app.analysis import analyze_one, sentiment, text_features
from fastapi.testclient import TestClient
from app.main import app
from app.train import split_without_duplicate_leakage


def test_sentiment_and_text_features_are_deterministic():
    text = "Excellent quality! I love this product."
    assert sentiment(text)["label"] == "positive"
    features = text_features(text)
    assert features["word_count"] == 6
    assert features["exclamation_count"] == 1


def test_rating_sentiment_mismatch_is_explained():
    result = analyze_one({"review_text": "Terrible and broken, I hate it.", "rating": 5})
    assert result["rating_sentiment_mismatch"] is True
    assert "Rating and text sentiment disagree" in result["signals"]


def test_behavioral_fields_are_only_reported_when_supplied():
    absent = analyze_one({"review_text": "An ordinary review."})
    present = analyze_one({"review_text": "An ordinary review.", "reviewer_id": "r-1"}, reviewer_count=6)
    assert absent["behavior"]["prior_reviews_by_reviewer"] is None
    assert present["behavior"]["prior_reviews_by_reviewer"] == 6
    assert any("earlier reviews" in signal for signal in present["signals"])


def test_near_duplicate_signal_is_batch_scoped():
    result = analyze_one({"review_text": "Really great product for my home."}, ["Really great product for my home."])
    assert result["behavior"]["closest_text_similarity"] == 1
    assert any("duplicate" in signal.lower() for signal in result["signals"])


def test_single_review_api_does_not_fabricate_model_output(monkeypatch):
    import app.main as main
    monkeypatch.setattr(main, "MODEL", None)
    monkeypatch.setattr(main, "MODEL_LOAD_ERROR", None)
    response = TestClient(app).post("/api/v1/analyze", json={
        "review_text": "Terrible product and broken", "rating": 5,
    })
    assert response.status_code == 200
    assert response.json()["rating_sentiment_mismatch"] is True
    assert response.json()["prediction"] is None
    assert response.json()["model_status"] == "not_trained"


def test_csv_batch_api_derives_duplicate_and_batch_behavior_signals():
    response = TestClient(app).post("/api/v1/analyze/batch", files={
        "file": ("reviews.csv", b"review_id,reviewer_id,rating,review_date,review_text\n"
                 b"a,r1,5,2026-01-01,Excellent quality and I love this item!\n"
                 b"b,r1,5,2026-01-01,Excellent quality and I love this item!\n"
                 b"c,r1,5,2026-01-02,Another review by the same reviewer.\n", "text/csv")
    })
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["model_status"] == "demo"
    assert body["results"][0]["behavior"]["prior_reviews_by_reviewer"] is None
    assert body["results"][1]["behavior"]["prior_reviews_by_reviewer"] is None
    assert body["results"][1]["behavior"]["same_day_reviews_by_reviewer_in_batch"] == 2
    assert body["results"][1]["behavior"]["closest_text_similarity"] == 1
    assert body["results"][1]["prediction"] in {"likely_genuine", "potentially_suspicious"}
    assert body["results"][2]["behavior"]["prior_reviews_by_reviewer"] == 2


def test_csv_batch_api_rejects_wrong_extension_and_missing_text_column():
    client = TestClient(app)
    wrong_type = client.post("/api/v1/analyze/batch", files={
        "file": ("reviews.txt", b"review_text\nhello\n", "text/plain")
    })
    missing_column = client.post("/api/v1/analyze/batch", files={
        "file": ("reviews.csv", b"rating\n5\n", "text/csv")
    })
    assert wrong_type.status_code == 415
    assert missing_column.status_code == 422


def test_single_review_api_rejects_empty_or_out_of_range_input():
    client = TestClient(app)
    empty = client.post("/api/v1/analyze", json={"review_text": "", "rating": 5})
    invalid_rating = client.post("/api/v1/analyze", json={"review_text": "Valid length text", "rating": 6})
    assert empty.status_code == 422
    assert invalid_rating.status_code == 422
    whitespace = client.post("/api/v1/analyze", json={"review_text": "   ", "rating": 5})
    assert whitespace.status_code == 422


def test_health_and_trained_demo_model_are_explicitly_marked():
    client = TestClient(app)
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["model_status"] == "demo"
    result = client.post("/api/v1/analyze", json={
        "review_text": "Amazing product! Best product ever, perfect quality, life changing! Five stars, must buy now! I recommend it 100%!",
        "rating": 5,
        "product_id": "demo-product-01",
        "reviewer_id": "demo-reviewer-01",
    })
    assert result.status_code == 200
    body = result.json()
    assert body["model_status"] == "demo"
    assert body["prediction"] == "potentially_suspicious"
    assert 0 <= body["risk_score"] <= 100
    assert body["product_id"] == "demo-product-01"
    assert body["reviewer_id"] == "demo-reviewer-01"


def test_corrupt_model_artifact_is_reported_as_load_error(monkeypatch, tmp_path, caplog):
    import app.main as main
    corrupt = tmp_path / "corrupt.joblib"
    corrupt.write_text("not a joblib artifact")
    monkeypatch.setattr(main, "MODEL_PATH", corrupt)
    model, metadata, error = main.load_model()
    assert model is None
    assert metadata == {}
    assert error
    assert "Could not load review model" in caplog.text


def test_training_holdout_keeps_normalized_exact_duplicates_together():
    texts = [f"review {i}" for i in range(20)]
    labels = [i % 2 for i in range(20)]
    # Add duplicate variants with the same label; whitespace/case normalization must group them.
    texts.extend(["  REVIEW   0 ", "review 1"])
    labels.extend([0, 1])
    train_idx, test_idx = split_without_duplicate_leakage(
        __import__("pandas").Series(texts), __import__("pandas").Series(labels))
    normalize = lambda value: " ".join(value.lower().split())
    train_groups = {normalize(texts[i]) for i in train_idx}
    test_groups = {normalize(texts[i]) for i in test_idx}
    assert train_groups.isdisjoint(test_groups)
    assert {labels[i] for i in train_idx} == {0, 1}
    assert {labels[i] for i in test_idx} == {0, 1}
