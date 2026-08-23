# 5-minute pitch script — SentinelPay

> Recording notes: terminal + dashboard side by side. Numbers below reference the trained model in this repo; re-check `artifacts/metrics.json` after retraining.

## 0:00–0:30 — Problem

"Merchants lose money to fraud three ways: blocked legitimate customers, missed fraud, and manual review backlogs nobody can explain. Razorpay's track asks for a working detector for one class of loss, with measured precision and recall, where every money action is explainable, bounded and gated. SentinelPay is exactly that — here's the working system."

## 0:30–1:15 — Architecture (30 seconds of diagram)

"One FastAPI engine. A transaction hits the feature engine: 21 behavioral features — velocity windows, geo mismatch, card age, spend ratios. A LightGBM model scores it. Seven deterministic velocity rules run beside it and can escalate but never de-escalate the decision. The combined action passes through a hard gate: above ₹40,000 the system is not allowed to auto-block — it escalates to a human. Then everything — transaction, score, reasons, SHAP attributions, explanation — lands in a SHA-256 hash-chained audit ledger."

## 1:15–2:15 — The numbers (why trust it)

"Time-based split — train on the past, test on the future, no leakage. PR-AUC 0.976 on data deliberately seeded with stealth fraud and hard negatives so the problem isn't trivially separable. The review tier operates at 96.7% recall with 74% precision — that's what humans see. The auto-block tier demands essentially perfect precision — 100% on our test set at 78% subset recall — because blocking a legit customer costs more than reviewing one. Thresholds aren't hand-picked; they're selected by F2 and cost sweeps on held-out data. There's also a rupee cost model: missed fraud value plus ₹150 friction per false positive picks the cheapest operating point."

## 2:15–3:45 — Live demo

1. Start the simulator. "Realistic traffic with injected attacks — card testing bursts, account takeover."
2. Live feed: "Green allows flow through. Here's an attack — card testing: six micro-charges then a big one. The CARD_TESTING_BURST rule fires, model score spikes, it's blocked."
3. Click into a REVIEW item: "SHAP gives the top drivers, the LLM writes the analyst narrative. When no LLM key is present it falls back to a template — same content, zero dependency."
4. Resolve as fraud: "The label is written to the ledger under my analyst identity and feeds retraining. One click runs the full training job and hot-swaps the model."
5. Audit page: "Every decision and every human action is hash-chained. Try editing a row in SQLite — verification pinpoints the exact broken sequence."

## 3:45–4:20 — Failure handling (the bar)

"Four graceful failures, all demonstrated: model can't load → safe mode routes everything to humans, nothing fails open. LLM down → circuit breaker, templates take over. High-value false positive → human gate instead of silent block. Ledger tampering → chain breaks visibly. Plus rate limiting and webhook alerts."

## 4:20–5:00 — Why me / close

"I chose boring, defensible technology — GBDTs over deep learning for tabular payments data — and spent the complexity budget on the things that make risk systems trustworthy: measured metrics on honest splits, bounded autonomy, explanations that survive an audit, and a feedback loop that improves the model from every analyst decision. The repo, tests, CI and deployment configs are public. Let's talk about how this plugs into Razorpay's risk stack."

---

### Demo checklist before recording
- [ ] Fresh DB, simulator started ~60s before recording so flagged items exist
- [ ] One BLOCK example visible (card-testing scenario)
- [ ] Audit verify badge green; keep a tampered copy ready if showing break detection
- [ ] `metrics.json` values match those quoted aloud
