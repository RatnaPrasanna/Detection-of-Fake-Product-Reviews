# LLM API decision for the review detector

Checked: 2026-10-06

## Recommendation

**Do not make a generative LLM API key a requirement for this project.** The core system should classify with a trained, evaluated supervised model and evidence-backed signals. The repository already has a TF-IDF + Logistic Regression trainer, but it currently has no labeled dataset or trained model artifact, so its prediction path is unavailable. An LLM key does not supply labels, train that classifier, validate accuracy, or create reviewer history.

If you want a hosted model for a college prototype, make it an optional add-on for a short natural-language explanation or for experimentation. Never let it invent reviewer behavior, set the risk score, or override the ML classifier. If the API fails or is rate-limited, the app should show the existing deterministic signal explanations.

## Feature-by-feature fit

| Project feature | LLM API needed? | Better fit |
|---|---|---|
| Fake/genuine prediction and calibrated risk | No | Train/evaluate the existing supervised model on labeled data; calibrate probabilities and report actual held-out metrics |
| Rating/sentiment mismatch | No | Deterministic comparison of rating to a sentiment classifier |
| Sentiment | No | A tested sentiment classifier or suitable local NLP model; current small lexicon is only a baseline |
| Review length, capitalization, punctuation, repetition | No | Existing deterministic feature extraction |
| Reviewer frequency, rating ratios, timing | No | Real historical records containing reviewer ID, rating, timestamp; an LLM cannot infer missing behavior |
| Product-level statistics/dashboard | No | SQL aggregation over stored review/analysis records |
| Exact duplicate detection | No | Normalization + hashes or existing duplicate logic |
| Semantic similarity | No generative LLM; an embedding model can help | Embeddings + cosine similarity, evaluated on duplicate pairs; NVIDIA lists a 1B embedding model with a free endpoint |
| Short explanation in plain language | Optional | Template from detected signals first; optional LLM may rewrite only supplied evidence |

## NVIDIA API options to try

The NVIDIA API Catalog currently marks these endpoints as free for prototyping:

1. **`nvidia/nemotron-3.5-lightning-30b-a3b`** — the best hosted chat-model candidate to benchmark for an optional explanation. NVIDIA describes it as its fastest 30B A3B MoE model; the model card says 30B total / 3B active parameters and speculative decoding for faster generation. Its model page marks a free endpoint available and provides an OpenAI-compatible example. These are model/vendor claims, not a latency guarantee for your network or account. [Model/API page](https://build.nvidia.com/nvidia/nemotron-3.5-lightning-30b-a3b/build), [model card](https://build.nvidia.com/nvidia/nemotron-3.5-lightning-30b-a3b/modelcard)
2. **`nemotron-3-embed-1b`** — the better task match if you later add semantic duplicate search. NVIDIA lists it as a 1B text embedding model for semantic search with a free endpoint. It is an embedding model, not a chat/generation model. [NVIDIA model catalog](https://build.nvidia.com/models?q=embed)

To get a key, sign in to [NVIDIA Build](https://build.nvidia.com/), open the selected model, and use **Get API Key**. NVIDIA says the API Catalog is for prototyping/evaluation; per-model limits vary with model and concurrent demand, and NVIDIA warns hosted free endpoints can have extended wait times under load. Therefore no hosted free endpoint can be promised as consistently low latency. [NVIDIA NIM FAQ](https://forums.developer.nvidia.com/t/nvidia-nim-faq/300317)

Benchmark the actual key and model from the backend deployment region using repeated short prompts; record median and p95 latency plus 429/timeouts. Keep generation short (`max_tokens` around 80–120) and disable reasoning for a simple explanation. The NVIDIA model-card sample enables reasoning and requests up to 16,384 output tokens; that configuration is unnecessary for this project and can increase response time.

## Safe integration shape if you choose to try it

- Call NVIDIA only from Python/FastAPI. Store `NVIDIA_API_KEY` in `backend/.env`; never put it in `NEXT_PUBLIC_*`, frontend source, or a checked-in file.
- Pass only the review text and already-computed signals needed for explanation. Do not send reviewer IDs or private account data.
- Ask for one short explanation constrained to the supplied signals. Keep the numeric risk/prediction from the trained ML model, not the generated prose.
- Add a feature flag, timeout, and fallback to template explanations. Do not block the main prediction path on the LLM.
- Read the current API trial and model terms before sending review data to the hosted endpoint. Hosted inference sends text outside your app; use public or appropriately de-identified data for the prototype.
- Do not connect hosted persistence or deploy the current unauthenticated write API publicly. Add authentication, authorization, rate limits, and secret management first.

## Inputs still needed for a credible backtest

1. A provenance-documented labeled CSV with `review_text` and binary `label` (1=suspicious, 0=likely genuine). Include `rating`, `reviewer_id`, `product_id`, and `review_date` where the dataset legitimately provides them.
2. If you want saved history: a Supabase project and the migration in `supabase/migrations/0001_initial.sql`, after the API is protected.
3. No marketplace API is required for the academic prototype. Such an API would only be needed if you want to ingest a particular platform's data, subject to its access rules and fields.
