# Architecture

## Components

### 1. Ingestion & normalization (`app/services/pipeline.py`)
Every transaction (API call or simulator) flows through one function: `process_transaction`.
It normalizes timestamps/refs, persists the raw transaction, then orchestrates scoring.

### 2. Feature engine (`app/ml/features.py`)
21 features computed identically online and offline:
- static: amount, log-amount, time-of-day sin/cos, day-of-week, night flag, CVV/AVS match, card age, IP↔billing country mismatch
- velocity: customer txn counts (1h / 24h), 24h sum/max, 30-day average, amount-vs-average ratio
- entity graphs (light): device txn count (7d), merchant hourly volume, prior confirmed fraud on the account

Training uses per-entity sorted arrays + binary search over nanosecond timestamps; online scoring queries the last 7 days from the DB. A parity test asserts both paths agree.

### 3. Detector (`app/ml/train.py`, `predict.py`)
LightGBM with `scale_pos_weight` for the 1% fraud rate, early stopping on a time-ordered validation slice. The `ModelRegistry` singleton loads artifacts once, supports hot reload after retraining, and computes exact TreeSHAP attributions per decision.

**Safe mode:** if artifacts are missing or corrupt, the registry reports unavailable and the pipeline routes everything to REVIEW with a `MODEL_UNAVAILABLE_SAFE_MODE` reason instead of failing open or closed blindly.

### 4. Rules layer (`app/engine/rules.py`)
Deterministic patterns with severity floors:

| Code | Trigger | Floor |
|---|---|---|
| CARD_TESTING_BURST | ≥5 micro-txns (<₹200) in 1h | BLOCK |
| VELOCITY_SPIKE | ≥4 txns in 1h | REVIEW |
| GEO_MISMATCH_HIGH_VALUE | foreign IP + ≥₹10k | REVIEW |
| NIGHT_LARGE_AMOUNT | 00–05h + ≥₹25k | REVIEW |
| NEW_CARD_HIGH_VALUE | card <2 days + ≥₹15k | BLOCK |
| DEVICE_FARM_SIGNAL | ≥40 txns/device in 7d | REVIEW |
| ACCOUNT_DRAIN_PATTERN | ≥12 txns in 24h | REVIEW |

`max_action(tier, floors)` — rules can escalate, never de-escalate.

### 5. Bounded autonomy (`hard gate`)
If the final action is BLOCK but `amount ≥ HARD_GATE_AMOUNT` (default ₹40k), the engine **downgrades to ESCALATE**: a human decides. Rationale: auto-blocking high-value legitimate commerce has asymmetric cost; the system's authority is explicitly bounded and the boundary is auditable.

### 6. Explanation layer
- SHAP top-3 stored synchronously on every decision (always available)
- LLM narrative generated asynchronously via a bounded thread pool; falls back to a deterministic template when no provider is configured, times out, or the circuit breaker is open

### 7. Audit ledger (`app/audit/ledger.py`)
Append-only table where each entry hashes `(seq, decision_id, actor, action_type, payload, prev_hash)` with SHA-256. Genesis prev_hash = 0x00*32. `/api/v1/audit/verify` recomputes the chain and pinpoints the first broken sequence. Analyst resolutions are entries with `actor=analyst:<name>` — humans are inside the audit perimeter too.

### 8. Feedback loop
Review outcomes set `Transaction.is_fraud` and persist analyst notes. `POST /admin/model/retrain` reruns the full training job in a background thread and atomically hot-swaps artifacts + thresholds, returning fresh held-out metrics under `/metrics/model`.

### 9. Drift monitor
Training stores quantile-bin histograms per numeric feature. `/metrics/drift` recomputes PSI on the latest 500 live decisions against those baselines; >0.25 raises an alert recommending retraining.

## Data flow (demo path)

```
simulator ─▶ POST pipeline ──▶ ALLOW (green feed)
    │              └──▶ rule/model flag ──▶ REVIEW ──▶ queue page ──▶ analyst resolve
    │                                            │                     │
    │                                            ▼                     ▼
    └──────────────────────▶ BLOCK ──▶ audit entry ──▶ webhook     retrain labels
```

## Deliberate non-goals
- Real payment-rail integration (Razorpay test-mode keys can be wired into the simulator without changing the engine)
- Distributed state (single-node SQLite by default; DATABASE_URL swaps to Postgres/Azure DB unchanged)
- Online learning (batch retrain keeps evaluation honest)
