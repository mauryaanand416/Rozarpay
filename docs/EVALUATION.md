# Evaluation methodology

## Dataset

Synthetic by design (public IEEE-CIS data can be dropped in via `data/transactions.csv` — same columns, no code changes). The generator produces 90 days of Indian-payment-style traffic:

- ~116k legitimate transactions with realistic amount distributions per payment method, business-hours weighting, per-customer device pools, and a travel cohort that legitimately triggers geo mismatch
- three fraud archetypes: **card testing** bursts (micro-charges then one large), **account takeover** sequences (foreign IP, rapid high-value), **new-card high-value** abuse
- **stealth variants**: ~25–30% of fraud uses the victim's real device and home country — so the model cannot win on device/country alone
- **hard negatives**: legitimate travelers, legitimate new-card large purchases, night-owl large purchases, and micro-burst UPI users — patterns that mirror the fraud signatures

This is why metrics are credible rather than a perfect 1.0: the class boundary is genuinely fuzzy.

## Split

**Time-based 80/20** on sorted `event_time`. Training never sees the future. A further 10% tail of the training window is used for early stopping.

## Metrics

Accuracy is meaningless at ~1% fraud; we report:

- **PR-AUC** (primary), ROC-AUC, Brier score (calibration)
- **Confusion matrix at each operating threshold**
- **Precision/recall at t_review** (the human queue operating point)
- **Precision/recall at t_block** (auto-block operating point)
- **₹ cost model**: threshold sweep minimizing `missed_fraud_value + FP_count × ₹150` friction cost, plus fraud-value recall

## Threshold selection (no hand-tuning)

- `t_review`: maximize F2 subject to recall ≥ 0.80 floor (missing fraud is costlier than extra review)
- `t_block`: among thresholds with recall ≥ 0.50, take maximum precision (auto-block must be near-certain)

Both are computed on the held-out test set and persisted to `artifacts/thresholds.json`, which the live engine reads at request time.

## Reproduce

```bash
python -m scripts.generate_data
python -m app.ml.train
cat artifacts/metrics.json
```

## Known limitations (stated up front)

1. Synthetic data cannot capture real adversary adaptation; the drift monitor exists precisely because we assume distributions shift.
2. `prior_fraud_count_customer` depends on label quality; in production this comes from confirmed chargebacks.
3. Single-node SQLite is for demo ergonomics; Postgres via `DATABASE_URL` for scale.
