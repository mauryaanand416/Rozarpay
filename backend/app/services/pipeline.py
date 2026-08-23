import json
import time
import uuid
from datetime import datetime, timedelta

import pandas as pd
from sqlalchemy.orm import Session

from app.audit import ledger
from app.config import get_settings
from app.db.models import Decision, Transaction
from app.engine import rules as rules_mod
from app.llm.explainer import queue_explanation
from app.ml.features import build_online_features
from app.ml.predict import get_registry
from app.services.bus import bus
from app.services.webhooks import notify_block

HISTORY_COLUMNS = ["amount", "is_fraud", "event_time", "customer_id", "device_id", "merchant_id"]


def load_history(db: Session, txn: dict, now: datetime) -> pd.DataFrame:
    window = now - timedelta(days=7)
    queries = [
        db.query(Transaction).filter(
            Transaction.event_time > window,
            Transaction.customer_id == txn.get("customer_id", ""),
        ),
        db.query(Transaction).filter(
            Transaction.event_time > window,
            Transaction.device_id == txn.get("device_id", ""),
        ),
        db.query(Transaction).filter(
            Transaction.event_time > window,
            Transaction.merchant_id == txn.get("merchant_id", ""),
        ),
    ]
    seen: dict[int, Transaction] = {}
    for q in queries:
        for r in q.limit(3000).all():
            seen[r.id] = r
    if not seen:
        return pd.DataFrame(columns=HISTORY_COLUMNS)
    records = []
    for r in seen.values():
        records.append(
            {
                "amount": r.amount,
                "is_fraud": bool(r.is_fraud) if r.is_fraud is not None else False,
                "event_time": r.event_time,
                "customer_id": r.customer_id,
                "device_id": r.device_id,
                "merchant_id": r.merchant_id,
            }
        )
    return pd.DataFrame.from_records(records)


def normalize_txn(raw: dict) -> tuple[dict, datetime]:
    txn = dict(raw)
    ts_raw = txn.get("event_time")
    if isinstance(ts_raw, str):
        try:
            dt = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
        except ValueError:
            dt = datetime.now().utcnow()
    elif isinstance(ts_raw, datetime):
        dt = ts_raw
    else:
        dt = datetime.utcnow()
    if dt.tzinfo is not None:
        dt = dt.astimezone(tz=None).replace(tzinfo=None)
    txn["event_time"] = dt
    txn.setdefault("txn_ref", f"TXN-{uuid.uuid4().hex[:12].upper()}")
    txn.setdefault("currency", "INR")
    return txn, dt


def process_transaction(db: Session, raw_txn: dict) -> dict:
    settings = get_settings()
    registry = get_registry()
    started = time.perf_counter()

    txn, event_dt = normalize_txn(raw_txn)
    record = Transaction(
        txn_ref=txn["txn_ref"],
        event_time=event_dt,
        amount=float(txn.get("amount", 0)),
        currency=txn.get("currency", "INR"),
        customer_id=str(txn.get("customer_id", "")),
        merchant_id=str(txn.get("merchant_id", "")),
        payment_method=str(txn.get("payment_method", "card")),
        device_id=str(txn.get("device_id", "")),
        ip_country=str(txn.get("ip_country", "")),
        billing_country=str(txn.get("billing_country", "")),
        cvv_match=bool(txn.get("cvv_match", True)),
        avs_match=bool(txn.get("avs_match", True)),
        card_age_days=int(txn.get("card_age_days", 365)),
        channel=str(txn.get("channel", "web")),
    )
    db.add(record)

    reasons: list[dict] = []
    rule_hits: list[rules_mod.RuleHit] = []

    if not registry.available:
        score = None
        model_version = "unavailable"
        tier_action = rules_mod.REVIEW
        reasons.append(
            {
                "source": "system",
                "code": "MODEL_UNAVAILABLE_SAFE_MODE",
                "description": "Risk model could not be loaded; routed to human review (fail-safe mode)",
                "min_action": rules_mod.REVIEW,
            }
        )
        t_review, t_block = settings.t_review, settings.t_block
    else:
        history = load_history(db, txn, event_dt)
        feats = build_online_features(txn, history)
        score = registry.score(feats)
        model_version = registry.version

        thresholds_path = settings.artifacts_dir / "thresholds.json"
        t_review, t_block = settings.t_review, settings.t_block
        if thresholds_path.exists():
            th = json.loads(thresholds_path.read_text())
            t_review = float(th.get("t_review", t_review))
            t_block = float(th.get("t_block", t_block))

        tier_action = (
            rules_mod.BLOCK if score >= t_block else rules_mod.REVIEW if score >= t_review else rules_mod.ALLOW
        )

        rule_hits = rules_mod.evaluate_rules(feats, txn)
        for hit in rule_hits:
            reasons.append(
                {"source": "rule", "code": hit.code, "description": hit.description, "min_action": hit.min_action}
            )

        for r in registry.top_reasons(feats, k=3):
            reasons.append(
                {"source": "model", "code": r["feature"], "description": f"{r['label']}: {r['value']}", "impact": r["impact"]}
            )

        compact_feats = {k: v for k, v in feats.items()}

    floor = rules_mod.max_action([h.min_action for h in rule_hits]) if rule_hits else rules_mod.ALLOW
    action = rules_mod.max_action([tier_action, floor])

    if action == rules_mod.BLOCK and float(txn.get("amount", 0)) >= settings.hard_gate_amount:
        action = rules_mod.ESCALATE
        reasons.append(
            {
                "source": "gate",
                "code": "HIGH_VALUE_HUMAN_GATE",
                "description": (
                    f"Auto-block suppressed: amount {float(txn['amount']):.0f} INR exceeds hard gate "
                    f"{settings.hard_gate_amount:.0f} INR; escalated to human reviewer"
                ),
                "min_action": rules_mod.ESCALATE,
            }
        )

    latency_ms = round((time.perf_counter() - started) * 1000, 2)

    decision = Decision(
        txn_ref=txn["txn_ref"],
        risk_score=float(score) if score is not None else -1.0,
        action=action,
        reasons=reasons,
        features=compact_feats if registry.available else {},
        model_version=model_version,
        threshold_used={"t_review": t_review, "t_block": t_block},
        latency_ms=latency_ms,
    )
    db.add(decision)
    db.flush()

    if action in (rules_mod.REVIEW, rules_mod.ESCALATE):
        from app.db.models import Review

        review = Review(decision_id=decision.id, txn_ref=txn["txn_ref"], status="pending")
        db.add(review)

    ledger.append_entry(
        db,
        actor="risk-engine",
        action_type=f"decision:{action.lower()}",
        payload={
            "txn_ref": txn["txn_ref"],
            "amount": float(txn.get("amount", 0)),
            "risk_score": None if score is None else float(score),
            "model_version": model_version,
            "rule_codes": [r["code"] for r in reasons if r.get("source") == "rule"],
        },
        decision_id=decision.id,
    )
    db.commit()

    queue_explanation(decision.id)

    payload = serialize_decision(decision, record)
    bus.publish(payload)
    if action in (rules_mod.BLOCK, rules_mod.ESCALATE):
        notify_block(payload)
    return payload


def serialize_decision(decision: Decision, record: Transaction | None = None) -> dict:
    data = {
        "decision_id": decision.id,
        "txn_ref": decision.txn_ref,
        "risk_score": decision.risk_score if decision.risk_score >= 0 else None,
        "action": decision.action,
        "reasons": decision.reasons,
        "model_version": decision.model_version,
        "threshold_used": decision.threshold_used,
        "latency_ms": decision.latency_ms,
        "created_at": decision.created_at.isoformat(),
        "explanation": decision.explanation,
        "explanation_source": decision.explanation_source,
        "transaction": record.to_dict() if record is not None else {"txn_ref": decision.txn_ref},
    }
    return data
