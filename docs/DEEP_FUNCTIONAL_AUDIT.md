# Deep functional audit

Audit date: 2026-10-06

## Architecture reconstructed

- Frontend: Next.js 15.5 / React 19 / TypeScript App Router; a single page currently contains review analysis and CSV upload.
- Backend: FastAPI / Python; authoritative signal extraction, optional model inference, CSV processing, optional Supabase persistence.
- Database: Supabase PostgreSQL schema migration is present. No Supabase project is configured in the environment.
- ML: TF-IDF word/bigram + balanced Logistic Regression trainer; no artifact or labeled dataset is present. The live process reports `model_status=unavailable` until a trained artifact is supplied.
- NLP: small English positive/negative term lexicon for sentiment; regex-based token/character features; exact/near duplicate comparison via `SequenceMatcher` within a batch.
- Authentication: absent. RLS is enabled and grants no browser role access; backend service-role use is optional.
- Data: no review dataset, provenance, labels, or user credentials were found.
- API: `/health`, `/api/v1/analyze`, `/api/v1/analyze/batch`, `/api/v1/dashboard`.
- Tests: backend unit/API tests. No frontend component or browser integration tests.

## Feature verification

Legend: ✅ verified working for the stated scope; 🟡 partial; ❌ missing; ⚠️ present but requires correction/validation.

| Feature | Status | Current implementation / evidence | Gap or required input |
|---|---|---|---|
| Authentication, profile, admin | ❌ | No auth routes, pages, or user tables | Choose an identity provider and add backend token verification/role policies before public data access |
| Single review input | 🟡 | Text + 1–5 rating; product/reviewer/date optional in backend schema | Frontend only exposes text/rating; product name, reviewer, date are not collected |
| Sentiment | 🟡 | Deterministic compact English lexicon; polarity score and positive/negative counts | Not robust NLP, no language detection, no calibration; neutral often means lexicon lacks a match |
| Text features | 🟡 | Length, words, sentences, uppercase ratio, punctuation, repeated words, promotional phrase count | Descriptive only; not consumed by classifier except TF-IDF text itself |
| Model training | 🟡 | CLI train/holdout split and metric calculation implemented | Cannot run responsibly without labeled data; no artifact exists; no model metrics are established |
| Model prediction / risk | ❌ until artifact | Uses positive class probability from a loaded sklearn pipeline and maps 0.5 to a binary label | No model available now; probability is not calibrated and must not be interpreted as fraud certainty |
| Model explanations | ❌ | Handwritten signal indicators only | No feature attribution for classifier output; current indicators do not drive ML score |
| Reviewer behavior | 🟡 | Prior-review count from strictly earlier dated rows; same-date cohort is marked as retrospective | No persistent history, rating ratios/variance, product count, inter-review interval, or global activity |
| Temporal/burst analysis | 🟡 | Dated rows are processed chronologically; same-date reviewer cohort threshold is 3 | No timestamp-level ordering, velocity windows, prior persistent history, or product-level velocity |
| Rating/sentiment mismatch | ✅ narrow scope | Rule compares 1–2 / 4–5 star bands with lexicon polarity; covered by test | Explicitly a heuristic alert, not model evidence; 3-star behavior is unclassified |
| Duplicate/similar text | 🟡 | SequenceMatcher across earlier rows in a single uploaded batch; tested for exact duplicates | No cross-product, persisted corpus, reviewer history, or semantic similarity; pairwise work scales quadratically |
| CSV upload and validation | 🟡 | API validates extension, 5 MB / 1,000 row limits, required review_text, ratings, and supplied review dates | No download/export; no client preview; optional fields such as verified_purchase and votes are not comprehensively type-validated; empty CSV behavior not user-tested |
| Product analysis | ❌ | Product ID can be carried on rows | No product page or product aggregate API |
| Dashboard | 🟡 | Backend aggregates configured `analyses` rows | No dashboard UI, rating distribution, suspicious reviewer/product statistics, or pagination; live Supabase unavailable |
| Database persistence | 🟡 | Migration and server-side Supabase read/write wrapper | Not live-tested; optional; no transactions or ownership model; configured writes store raw review text |
| API validation/errors | ✅ basic | Pydantic validation, CSV limits, status codes, client error rendering; API tests pass | Generic DB failure handling; no auth/rate limiting/request quotas |
| UI responsiveness | ⚠️ | CSS has responsive breakpoints; typecheck and production build pass | No visual/browser testing because browser access was declined; build emits autoprefixer compatibility warnings |
| Security/privacy | ⚠️ not deployment-ready | No browser service-role key; RLS enabled and no anon/auth grants; file bounds and local CORS default | API is unauthenticated. If Supabase service credentials are configured and API is exposed publicly, callers can trigger writes using privileged credentials. Keep local only until auth/rate limiting and deployment controls exist |

## Functional backtesting results

- Backend suite: **9 passed** (`python3 -m pytest tests -q`). Tests cover deterministic sentiment/features, mismatch, missing/present batch reviewer data, duplicate detection, single-review unavailable-model behavior, valid batch behavior, invalid CSV shape/type, invalid single-review input, and duplicate-group isolation in the training split.
- Python compile check: **passed** (`python3 -m compileall -q app tests`).
- Frontend typecheck: **passed** (`npm run typecheck`).
- Production build: **passed** (`npm run build`) with three CSS autoprefixer warnings about `start`/`end` flex alignment support. Build and typecheck prove compilation, not browser functionality.
- Model behavior: **not backtested**. No genuine labeled dataset or model artifact was available. Training on invented/example labels would not be evidence of performance.
- Leakage checks: normalized exact duplicates are grouped into one train/test side; a unit test verifies disjoint groups. Semantically similar campaign leakage and future-period generalization still require dataset-level checks.
- Supabase: **not integration-tested**. No URL/key or migration target was provided.
- Browser E2E: **not run**. Browser access to localhost was explicitly declined by browser permission controls. No workaround was attempted.

## Findings to address before claiming project completion

### P0 — Core validity and safe connection

1. Provide a provenance-documented CSV with at least `review_text` and verified binary `label` (0=likely genuine, 1=suspicious); ideally include product/reviewer/time fields. The trainer now uses a deterministic group-disjoint holdout for normalized exact duplicates. It does not catch semantic campaign overlap or evaluate future-period generalization, so inspect those risks before reporting metrics.
2. Train the model and record actual precision, recall, F1, confusion matrix, and ROC AUC from the held-out split. Assess class balance and duplicate leakage first.
3. Do not expose the API with Supabase service-role credentials until authentication/authorization, rate limiting, and persistence access controls exist. Current routes are public and unauthenticated.

### P1 — Important for stated workflows

1. Add product/reviewer/date fields to the frontend and return the derived signals visibly.
2. Build dashboard and product-level aggregate UI/endpoints from persisted records; add paging and avoid fetching the entire table in one query.
3. Add CSV preview and result export; validate optional schema fields and bad dates/IDs.
4. Add persistent reviewer/window behavior, corpus-level similarity, and proper model-linked explanations where evidence supports them.
5. Add database integration tests and browser E2E tests, then exercise the whole flow after connecting the services.

### P2 — Optional enhancements

- Semantic embeddings, campaign graph detection, trust-adjusted ratings, SHAP, AI-generated text indicators, and marketplace integrations. These are not necessary for the minimum demo and need data/evaluation justification.

## What you need to connect

No third-party marketplace API is required for the current research prototype. The minimum external inputs are:

1. **Labeled review dataset** for model training. Required: `review_text`, `label`; recommended: `rating`, `product_id`, `reviewer_id`, `review_date`, `review_title`, `verified_purchase`. Labels and provenance must be trustworthy.
2. **Supabase project** only if persistence/dashboard history is needed. Apply the migration, then provide `SUPABASE_URL` and a server-only `SUPABASE_SERVICE_ROLE_KEY` in `backend/.env` (never `NEXT_PUBLIC_*`). Do not expose the unauthenticated write API publicly after doing this.
3. **Authentication provider** before real user or public deployment. Supabase Auth is a plausible match but is not set up; the backend must verify bearer tokens and enforce ownership/roles, with RLS policies and user ownership columns designed accordingly.

The frontend only needs the Python API URL via `NEXT_PUBLIC_API_URL` when not using `http://localhost:8000`.
