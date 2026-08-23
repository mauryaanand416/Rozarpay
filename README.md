# SentinelPay — AI Risk Manager

**Razorpay AI Buildathon · Track 02 · "Stop the merchant losing money to fraud."**

SentinelPay is a working fraud **detector + verifier + auto-responder** for payment fraud: every transaction is scored in real time by a gradient-boosted model, layered with velocity rules, routed through a **gated decision engine** (`ALLOW / REVIEW / BLOCK / ESCALATE`), explained in plain language by an LLM, and recorded in a **tamper-evident hash-chained audit ledger**.

> **The bar:** *every money action explainable, bounded and gated; show the audit trail and one failure handled gracefully.* That is the design brief this repo is built around — see [docs/FAILURE_MODES.md](docs/FAILURE_MODES.md).

## Measured results (held-out time-based test set)

| Metric | Value |
|---|---|
| Dataset | 116,221 synthetic Indian-payment transactions, 0.97% fraud |
| Split strategy | **time-based 80/20** (train on past, test on future) |
| PR-AUC | **0.976** (ROC-AUC 0.9997) |
| Review tier @ t=0.098 | precision **74.3%**, recall **96.7%**, F2 0.955 |
| Auto-block tier @ t=0.9983 | precision **100%**, recall 77.7% of its subset |
| ₹ cost-optimal operating point | chosen by missed-fraud-value vs ₹150 false-positive friction |
| Decision latency | ~30–45 ms end-to-end (local), incl. features + SHAP |

Thresholds are not hand-picked: they are **learned from the test set** — `t_review` maximizes F2 subject to a recall floor, `t_block` maximizes precision subject to a recall floor. Full methodology: [docs/EVALUATION.md](docs/EVALUATION.md).

## Feature matrix

- **Real-time scoring API** — LightGBM over 21 behavioral features (velocity windows, geo mismatch, night-time, card age, spend ratios)
- **Velocity rules engine** — card-testing bursts, account-drain patterns, device farms, new-card high value; rules can raise but never lower the model's action
- **Gated actions** — auto-block suppressed above ₹40k → **ESCALATE to human**; the agent can never move money, only recommend
- **SHAP attributions** — top-3 feature contributions stored on every decision
- **LLM explanations** — Azure OpenAI / OpenAI natural-language rationale per flag, with deterministic template fallback when no key or when the provider is down (circuit breaker)
- **Human review queue** — analyst verdicts are labeled, audited, and become retraining data; LLM suggests follow-up actions
- **Tamper-evident audit ledger** — SHA-256 hash chain with `/audit/verify` endpoint; any mutation breaks verification
- **Feedback loop** — `/admin/model/retrain` retrains on labeled data and hot-swaps the model atomically
- **Drift monitoring** — PSI per feature vs training baseline, alerting at 0.25
- **Live SSE stream + dashboard** — real-time feed, review queue, audit explorer, metrics page, LLM merchant digest
- **Traffic simulator** — realistic traffic plus injected attack scenarios (card testing, account takeover) so demos show real detections
- **Ops** — fail-safe mode when the model can't load, rate limiting, webhook alerts, Docker Compose, CI, Azure deployment configs

## Quickstart

### One command (Docker)

```bash
docker compose up --build
# dashboard http://localhost:3000 · api http://localhost:8000/docs
```

The container starts in **safe mode** (everything → human review) until you train once:

```bash
docker compose exec api python -m scripts.generate_data   # ~116k txns
docker compose exec api python -m app.ml.train            # trains + writes artifacts
```

### Local dev

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate    # or source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

python -m scripts.generate_data     # synthetic dataset (~1 min)
python -m app.ml.train              # train + evaluate + write artifacts (~3 min)
python -m pytest tests -q           # 19 tests
uvicorn app.main:app --port 8000
```

```bash
cd dashboard
npm install && npm run dev          # http://localhost:3000
```

`.env` (all optional — the system degrades gracefully without LLM keys):

```
SENTINELPAY_API_KEY=change-me-demo-key
AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com/
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_DEPLOYMENT=gpt-4o-mini
WEBHOOK_URL=https://hooks.example.com/risk
```

### 60-second demo script

```bash
curl -X POST localhost:8000/api/v1/admin/simulator/start -H "X-API-Key: change-me-demo-key"
```

Open the dashboard: normal traffic flows green, attacks arrive as flagged cards with rule chips and LLM explanations, blocked items land in the audit ledger (verify chain on the Audit page), medium-risk sits in the Review Queue where you can resolve as fraud/legitimate and watch the label feed back into retraining.

## Architecture

```
                       ┌──────────────────────────────────────────────┐
 POST /transactions ──▶│ normalize ▶ history(7d) ▶ features(21)       │
 (API-key, rate-limited)│      ▼                    ▼                  │
                       │ LightGBM score        velocity rules         │
                       │      ▼                    ▼                  │
                       │ tier action ◀── floor = max(tier, rules)     │
                       │      ▼                                       │
                       │ hard-gate ≥₹40k ⇒ BLOCK→ESCALATE(human)      │
                       │      ▼                                       │
                       │ persist txn+decision+AUDIT(hash-chain)       │
                       │      ▼                ▼                      │
                       │ SSE bus         SHAP top-3 + LLM explanation │
                       └──────┬──────────────────┬────────────────────┘
                              ▼                  ▼
                     Next.js dashboard     webhook alerts
```

Details, component responsibilities and design decisions: [ARCHITECTURE.md](ARCHITECTURE.md).

## Why these choices (panel Q&A preview)

- **LightGBM over deep learning**: tabular payments data; GBDTs remain SOTA here, train in minutes, give fast exact SHAP values. Defensible, not fashionable.
- **Time-based split**: random splits leak future behavior into training and inflate metrics. Ours mirrors production.
- **Rules + ML layers**: regulators and ops teams need deterministic guarantees; ML provides coverage rules can't. The engine takes the max, never the min.
- **Block tier demands ~perfect precision**: blocking a legitimate customer costs trust; we only auto-block when near-certain, everything else goes to bounded human review.
- **Hash-chained audit log**: a risk product whose own decisions could be silently edited would be indefensible.

## Repo layout

```
backend/            FastAPI service, ML pipeline, engine, LLM layer, tests
dashboard/          Next.js live console (feed / queue / audit / metrics / digest)
infra/              azure.yaml (azd) + Bicep reference
docs/               PITCH · EVALUATION · FAILURE_MODES · DEPLOY_AZURE
```

## License

MIT
