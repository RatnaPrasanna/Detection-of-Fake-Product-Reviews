# Fake Product Review Detection

An explainable decision-support prototype for assessing review risk from text, rating consistency, review timing, reviewer history, and similarity. A risk assessment is not proof of fraud.

## Current state

This workspace was empty at project start. The current implementation is a local development foundation: a Python API extracts text and sentiment signals and can train a scikit-learn classifier from a supplied labeled CSV; a Next.js interface supports single review and CSV batch analysis; a PostgreSQL/Supabase migration defines persistent tables and access policies.

The API does not invent a trained model, evaluation metrics, stored records, user identities, or dashboard counts. Until a model is trained from appropriately labeled data, inference is marked unavailable and the API returns feature analysis without a fabricated model prediction. Supabase persistence is activated only when configured.

## Architecture

```text
Next.js / TypeScript → FastAPI / Python → Supabase PostgreSQL (optional until configured)
                                  └→ scikit-learn model artifact (trained locally)
```

Python owns analysis and model inference. The frontend owns presentation. The SQL migration is the database source of truth. The development UI is not an authentication system; deploy behind a configured identity provider before exposing private data.

## Requirements

- Python 3.11+
- Node.js 20+
- A labeled CSV to train a classifier; labels must be provided by the data owner.
- Supabase project and credentials only if persistent storage is needed.

## Run locally

Backend:

```sh
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend:

```sh
cd frontend
npm install
npm run dev
```

Set `NEXT_PUBLIC_API_URL=http://localhost:8000` in `frontend/.env.local` if using a different API address. Backend configuration is documented in `backend/.env.example`.

## Train a model

The training CSV must contain `review_text` and a user-verified binary `label` column (1=suspicious, 0=likely genuine). Optional columns include `rating`, `product_id`, `reviewer_id`, and `review_date`. Use a source with documented provenance and inspect label quality and leakage before training. The holdout groups normalized exact duplicate text together; this does not eliminate semantic campaign overlap or evaluate future-period generalization.

```sh
cd backend
python -m app.train --data /path/to/labeled_reviews.csv --output artifacts/review_model.joblib
```

The command prints holdout precision, recall, F1, ROC AUC when defined, and a confusion matrix. Metrics describe that dataset split only. Keep the generated artifact out of source control and set `MODEL_PATH` to load it. No model or evaluation result is bundled with this empty-repository baseline.

## Local demo model and test data

This repository includes `backend/data/synthetic_demo_reviews.csv`, a generated 60-row dataset for interface and API smoke testing only. It is deliberately patterned and is not real-world evidence. Its trained artifact is generated locally and git-ignored. From `backend/`, run:

```sh
.venv/bin/python -m app.train --data data/synthetic_demo_reviews.csv --output artifacts/review_model.joblib --model-type synthetic_demo
```

Then restart the backend. `/health` reports `model_status: demo`, and analysis responses retain that status so the UI can warn that predictions are not meaningful. The frontend also links to a copy of the CSV for batch upload. Never present its metrics or scores as validated detection performance; use a provenance-labeled, representative dataset for that.

## CSV analysis

Batch CSV requires a `review_text` column. Supported optional columns: `review_id`, `product_id`, `reviewer_id`, `rating` (1–5), `review_date`, `review_title`, `verified_purchase`, `helpful_votes`, `total_votes`. Rows missing optional behavioral data are analyzed without those signals. CSV uploads are size and row limited by the API.

## API

- `GET /health` — API and model availability.
- `POST /api/v1/analyze` — analyze one review.
- `POST /api/v1/analyze/batch` — multipart CSV analysis.
- `GET /api/v1/dashboard` — persisted aggregate counts; returns empty counts until configured and populated.

Interactive API docs are served at `/docs` in development.

## Database setup

Apply `supabase/migrations/0001_initial.sql` to a Supabase project. Configure `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` on the backend only. Never expose the service-role key in browser variables. The schema enables RLS and denies anonymous access; policies grant no user access until an authenticated identity integration and scoped policies are deliberately added. Backend service-role operations bypass RLS and must only be exposed through an authorized backend.

## Limitations and next steps

- A labeled, representative dataset is required for trained classification and credible evaluation.
- Sentiment is a transparent compact lexicon baseline, not a validated language model.
- Similarity in the initial analyzer uses normalized exact/near duplicate checks, not semantic embeddings.
- Reviewer and temporal features are computed only from rows supplied in the same batch or available persisted history.
- Authentication, user profile, admin role management, campaign detection, semantic similarity, trust-adjusted product rating, deployment, and end-to-end integration remain incomplete.
- Public data can have weak or platform-specific labels; cross-domain behavior and drift need evaluation.
- Genuine unusual reviews may receive high risk scores. Suspicious does not mean confirmed fraudulent.
