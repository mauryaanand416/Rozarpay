# Failure modes — handled gracefully

The buildathon bar: *"Show the audit trail and one failure handled gracefully."*
Here are four, each demonstrable live.

## 1. Model unavailable at startup → SAFE MODE (fail-safe, not fail-open)

**Trigger:** delete/rename `backend/artifacts/` and start the API.

**Behavior:** `/healthz` reports `safe_mode: true`; every transaction is routed to **REVIEW**
with reason `MODEL_UNAVAILABLE_SAFE_MODE`. No transaction is silently allowed, nothing crashes,
the dashboard shows an amber banner. The audit ledger records the degraded decision like any other.

```
curl localhost:8000/healthz
{"status":"ok","safe_mode":true,"model":{"available":false,...}}
```

## 2. LLM provider down → circuit breaker + template explanations

**Trigger:** invalid `AZURE_OPENAI_API_KEY` (or no key at all).

**Behavior:** after 3 consecutive failures the breaker opens for 60s; explanation generation
falls back to a deterministic template built from rules + score. Decisions keep flowing with
zero added latency beyond the timeout budget. The dashboard marks LLM-sourced vs template text.

## 3. False positive on a high-value legitimate order → human gate, never silent loss

**Trigger:** simulate a ₹60k order that scores above `t_block`.

**Behavior:** the engine refuses to auto-block above the hard gate (`₹40k`): action becomes
**ESCALATE**, reason `HIGH_VALUE_HUMAN_GATE`, a review is queued, and the webhook fires.
A human releases or blocks it; both outcomes are audited with the analyst's name.

## 4. Audit tampering → chain verification pinpoints the break

**Trigger:** any direct DB edit of a historical entry (see test `test_tamper_detection`).

**Behavior:** `GET /api/v1/audit/verify` recomputes hashes and returns

```json
{"valid": false, "broken_at_seq": 2, "reason": "entry tampered"}
```

The dashboard turns the chain badge red. Silent history edits are detectable by construction.

## Bonus hardening

- Rate limiting (429) protects scoring endpoints from abuse
- Webhook delivery failures are logged, never propagated to the decision path
- Retraining runs in a guarded background thread; concurrent retrains are rejected with HTTP 409
- Feature-parity tests guarantee online features match training semantics
