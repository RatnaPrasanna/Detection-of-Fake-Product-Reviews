"""Train and evaluate a text classifier from an explicitly labeled CSV."""
import argparse
import json
import re
from pathlib import Path

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, classification_report, confusion_matrix,
                             f1_score, precision_score, recall_score, roc_auc_score)
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline


def split_without_duplicate_leakage(texts: pd.Series, labels: pd.Series) -> tuple[list[int], list[int]]:
    """Choose a deterministic, group-disjoint holdout for normalized exact duplicates."""
    groups = texts.map(lambda text: re.sub(r"\s+", " ", str(text).lower()).strip())
    splitter = GroupShuffleSplit(n_splits=50, test_size=0.2, random_state=42)
    best: tuple[float, list[int], list[int]] | None = None
    prevalence = float(labels.mean())
    for train_idx, test_idx in splitter.split(texts, labels, groups):
        if set(labels.iloc[train_idx]) != {0, 1} or set(labels.iloc[test_idx]) != {0, 1}:
            continue
        test_prevalence = float(labels.iloc[test_idx].mean())
        score = abs(len(test_idx) / len(labels) - 0.2) + abs(test_prevalence - prevalence)
        if best is None or score < best[0]:
            best = (score, train_idx.tolist(), test_idx.tolist())
    if best is None:
        raise SystemExit("Cannot form a group-disjoint holdout with both labels in train and test; supply more distinct labeled reviews")
    return best[1], best[2]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--output", default="artifacts/review_model.joblib")
    parser.add_argument("--model-type", choices=("trained", "synthetic_demo"), default="trained")
    args = parser.parse_args()
    frame = pd.read_csv(args.data)
    if not {"review_text", "label"}.issubset(frame.columns):
        raise SystemExit("CSV must contain review_text and label columns")
    frame = frame.dropna(subset=["review_text", "label"])
    frame["review_text"] = frame["review_text"].astype(str).str.strip()
    frame = frame[frame.review_text.str.len() >= 3].reset_index(drop=True)
    frame["label"] = pd.to_numeric(frame["label"], errors="raise").astype(int)
    if set(frame.label.unique()) != {0, 1} or frame.label.value_counts().min() < 2:
        raise SystemExit("label must contain both classes 0 and 1, with at least 2 rows per class")
    texts = frame.review_text.astype(str)
    train_idx, test_idx = split_without_duplicate_leakage(texts, frame.label)
    x_train, x_test = texts.iloc[train_idx], texts.iloc[test_idx]
    y_train, y_test = frame.label.iloc[train_idx], frame.label.iloc[test_idx]
    model = Pipeline([("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1,
                                                       max_features=50000, sublinear_tf=True)),
                      ("classifier", LogisticRegression(max_iter=1000, class_weight="balanced"))])
    model.fit(x_train, y_train)
    prediction = model.predict(x_test)
    probability = model.predict_proba(x_test)[:, list(model.classes_).index(1)]
    metrics = {"rows": int(len(frame)), "train_rows": int(len(x_train)), "test_rows": int(len(x_test)),
               "split_method": "group-disjoint exact duplicate holdout (GroupShuffleSplit)",
               "accuracy": accuracy_score(y_test, prediction),
               "precision": precision_score(y_test, prediction, zero_division=0),
               "recall": recall_score(y_test, prediction, zero_division=0),
               "f1": f1_score(y_test, prediction, zero_division=0),
               "roc_auc": roc_auc_score(y_test, probability),
               "confusion_matrix_labels_0_1": confusion_matrix(y_test, prediction, labels=[0, 1]).tolist(),
               "classification_report": classification_report(y_test, prediction, zero_division=0, output_dict=True)}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"pipeline": model, "metadata": {"metrics": metrics, "positive_label": 1,
                                                    "model_type": args.model_type}}, output)
    print(json.dumps(metrics, indent=2))
    print(f"Saved model artifact to {output}")


if __name__ == "__main__":
    main()
