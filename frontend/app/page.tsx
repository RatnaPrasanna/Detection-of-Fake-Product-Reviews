"use client";

import { ChangeEvent, FormEvent, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
type Analysis = {
  prediction: string | null; risk_score: number | null; model_status: string;
  sentiment: { label: string; score: number }; signals: string[];
  features: Record<string, number>; rating_sentiment_mismatch: boolean;
  product_id?: string | null; reviewer_id?: string | null;
  behavior?: { prior_reviews_by_reviewer: number | null; same_day_reviews_by_reviewer_in_batch: number | null; closest_text_similarity: number };
};
type BatchResult = { review_id?: string | null; sentiment?: { label: string }; prediction?: string | null; risk_score?: number | null; behavior?: Analysis["behavior"]; signals?: string[] };

export default function Home() {
  const [text, setText] = useState("");
  const [rating, setRating] = useState("5");
  const [productId, setProductId] = useState("");
  const [reviewerId, setReviewerId] = useState("");
  const [result, setResult] = useState<Analysis | null>(null);
  const [batch, setBatch] = useState<BatchResult[]>([]);
  const [batchModelStatus, setBatchModelStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError(""); setResult(null);
    try {
      const response = await fetch(`${API}/api/v1/analyze`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ review_text: text, rating: Number(rating), product_id: productId || null, reviewer_id: reviewerId || null }) });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? "Analysis failed. Check that the API is running.");
      setResult(body);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not reach analysis API."); }
    finally { setBusy(false); }
  }

  async function upload(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]; if (!file) return;
    setBusy(true); setError(""); setBatch([]); setBatchModelStatus(""); setResult(null);
    try {
      const form = new FormData(); form.append("file", file);
      const response = await fetch(`${API}/api/v1/analyze/batch`, { method: "POST", body: form });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? "Batch analysis failed.");
      setBatch(body.results ?? []); setBatchModelStatus(body.model_status ?? "not_trained");
    } catch (err) { setError(err instanceof Error ? err.message : "Could not reach analysis API."); }
    finally { setBusy(false); e.target.value = ""; }
  }

  return <main className="shell">
    <header className="topbar"><a className="brand" href="#"><span className="brand-mark">R</span> REVIEW INTEGRITY</a><span className="top-note">RESEARCH DECISION SUPPORT</span></header>
    <section className="hero"><div><div className="eyebrow"><span className="pulse"/> REVIEW SIGNAL ANALYSIS</div><h1>Trust is built<br/><em>one signal at a time.</em></h1><p className="lede">Explore review text, sentiment and available behavior for signs that deserve a closer look.</p></div>
      <aside className="hero-note"><span className="note-line"/><div><strong>Evidence over certainty</strong><p>Signals indicate review risk. They do not prove fraud.</p></div><span className="note-index">01 / 02</span></aside></section>
    <section className="workspace">
      <div className="panel form-panel"><div className="panel-head"><div><span className="section-number">01</span><h2>Analyze a review</h2></div><span className="live-tag">● API ANALYSIS</span></div>
        <form onSubmit={submit}><label htmlFor="review">REVIEW TEXT</label><textarea id="review" value={text} onChange={e => setText(e.target.value)} placeholder="Paste the review text you want to assess…" minLength={3} maxLength={10000} required/><div className="field-row"><div className="field"><label htmlFor="rating">STAR RATING</label><select id="rating" value={rating} onChange={e => setRating(e.target.value)}>{[5,4,3,2,1].map(n => <option key={n} value={n}>{n} {n === 1 ? "star" : "stars"}</option>)}</select></div><div className="field"><label htmlFor="product-id">PRODUCT ID (OPTIONAL)</label><input className="text-field" id="product-id" value={productId} onChange={e => setProductId(e.target.value)} maxLength={200} placeholder="e.g. product-42"/></div><div className="field"><label htmlFor="reviewer-id">REVIEWER ID (OPTIONAL)</label><input className="text-field" id="reviewer-id" value={reviewerId} onChange={e => setReviewerId(e.target.value)} maxLength={200} placeholder="e.g. reviewer-17"/></div></div><button className="primary" disabled={busy}>{busy ? "Analyzing…" : "Analyze review"}<span>↗</span></button></form>
        <div className="divider"><span>OR ANALYZE A DATASET</span></div><label className="upload"><span className="upload-icon">↑</span><span><strong>Upload a CSV file</strong><small>Needs a <code>review_text</code> column · 5 MB max</small></span><input type="file" accept=".csv,text/csv" onChange={upload} disabled={busy}/><span className="upload-arrow">↗</span></label><a className="demo-download" href="/synthetic_demo_reviews.csv" download>Download 60-row synthetic test CSV <span>↗</span></a>
      </div>
      <div className="panel result-panel"><div className="panel-head"><div><span className="section-number">02</span><h2>Assessment</h2></div><span className="status-tag">{result || batch.length ? "COMPLETE" : "AWAITING INPUT"}</span></div>
        {error && <div className="error" role="alert">{error}</div>}
        {!result && !batch.length && <div className="empty"><div className="empty-mark">◎</div><strong>Your analysis will appear here</strong><p>Submit a review or upload a CSV to see sentiment, risk assessment and the signals behind it.</p><div className="empty-rule"/></div>}
        {result && <div className="assessment" aria-live="polite"><div className="assessment-top"><div><span className="micro">MODEL CLASSIFICATION</span><h3>{result.prediction ? result.prediction.replaceAll("_", " ") : result.model_status === "load_error" ? "Model failed to load" : "Model not trained"}</h3></div><div className="risk"><span>{result.risk_score === null ? "—" : `${result.risk_score}`}</span><small>{result.risk_score === null ? "NO SCORE" : "RISK / 100"}</small></div></div><div className="meter"><i style={{ width: `${result.risk_score ?? 0}%` }}/></div><div className="summary-grid"><div><span>SENTIMENT</span><strong>{result.sentiment.label}</strong></div><div><span>MODEL</span><strong>{result.model_status.replaceAll("_", " ")}</strong></div><div><span>RATING MISMATCH</span><strong>{result.rating_sentiment_mismatch ? "Detected" : "None"}</strong></div></div><h4>OBSERVED SIGNALS</h4>{result.signals.length ? <ul className="signals">{result.signals.map(s => <li key={s}>{s}</li>)}</ul> : <p className="quiet">No listed signals found in the supplied information.</p>}<div className="caveat">{result.model_status === "demo" ? "DEMO MODEL: trained only on generated test examples. Scores are for interface testing and have no real-world validity. Replace with a provenance-labeled dataset before interpreting predictions." : result.model_status === "load_error" ? "The model artifact exists but could not be loaded. Check the backend log and model path." : result.model_status === "not_trained" ? "No model artifact is installed, so no fake/genuine classification was made. Text features are descriptive signals only." : "Predictions are risk indicators, not proof of fraud. Validate on representative, independently labeled reviews."}</div></div>}
        {result?.reviewer_id && <p className="quiet behavior-note">Reviewer activity history is not connected. Supplying an ID alone does not provide historical behavior.</p>}
        {batch.length > 0 && <div className="batch-results"><strong>{batch.length} reviews analyzed</strong><div className="batch-scroll"><table><thead><tr><th>Review</th><th>Sentiment</th><th>Prediction</th><th>Risk</th><th>Behavior in supplied batch</th></tr></thead><tbody>{batch.map((r,i) => <tr key={i}><td>{String(r.review_id ?? `Row ${i + 1}`)}</td><td>{String(r.sentiment?.label ?? "—")}</td><td>{String(r.prediction ?? "Model unavailable")}</td><td>{r.risk_score == null ? "—" : `${r.risk_score}%`}</td><td>{r.behavior?.prior_reviews_by_reviewer != null ? `${r.behavior.prior_reviews_by_reviewer} earlier` : (r.behavior?.same_day_reviews_by_reviewer_in_batch ?? 0) >= 2 ? `${r.behavior?.same_day_reviews_by_reviewer_in_batch} same-day in CSV` : "No prior activity"}</td></tr>)}</tbody></table></div><div className="caveat">{batchModelStatus === "demo" ? "DEMO MODEL: predictions use generated examples and are only for interface testing; scores have no real-world validity. Behavior values come only from this uploaded CSV; no external reviewer history is connected." : batchModelStatus === "load_error" ? "The model artifact exists but failed to load. Check the backend logs. Behavior values come only from this uploaded CSV." : batchModelStatus === "not_trained" ? "No model is available; only descriptive signals were analyzed. Behavior values come only from this uploaded CSV." : "Behavior values are calculated only from rows in this uploaded CSV; no external reviewer history is connected."}</div></div>}
        <div className="panel-foot"><span>REVIEW INTEGRITY / V 0.1</span><span>ASSESSMENT ≠ PROOF</span></div>
      </div>
    </section>
    <footer><span>AN EXPLAINABLE RESEARCH PROTOTYPE</span><span>MODEL RESULTS REQUIRE LABELED TRAINING DATA</span><span>◌ LOCAL SESSION</span></footer>
  </main>;
}
