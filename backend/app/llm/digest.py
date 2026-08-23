from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import Decision, Digest, Transaction


def collect_stats(db: Session, hours: int = 24) -> dict:
    since = datetime.utcnow() - timedelta(hours=hours)
    base = db.query(Decision).filter(Decision.created_at > since)

    total = base.count()
    by_action = dict(db.query(Decision.action, func.count()).filter(Decision.created_at > since).group_by(Decision.action).all())
    avg_latency = db.query(func.avg(Decision.latency_ms)).filter(Decision.created_at > since).scalar() or 0.0
    blocked_value = (
        db.query(func.sum(Transaction.amount))
        .join(Decision, Decision.txn_ref == Transaction.txn_ref)
        .filter(Decision.created_at > since, Decision.action.in_(["BLOCK", "ESCALATE"]))
        .scalar()
        or 0.0
    )
    review_value = (
        db.query(func.sum(Transaction.amount))
        .join(Decision, Decision.txn_ref == Transaction.txn_ref)
        .filter(Decision.created_at > since, Decision.action == "REVIEW")
        .scalar()
        or 0.0
    )

    top_rules: dict[str, int] = {}
    for (reasons,) in db.query(Decision.reasons).filter(Decision.created_at > since).all():
        for r in reasons or []:
            if r.get("source") == "rule":
                top_rules[r["code"]] = top_rules.get(r["code"], 0) + 1

    return {
        "window_hours": hours,
        "total_transactions": total,
        "by_action": by_action,
        "avg_latency_ms": round(float(avg_latency), 1),
        "blocked_or_escalated_value_inr": round(float(blocked_value), 2),
        "review_queue_value_inr": round(float(review_value), 2),
        "top_rule_hits": dict(sorted(top_rules.items(), key=lambda kv: kv[1], reverse=True)[:6]),
    }


def generate_digest(db: Session, hours: int = 24) -> dict:
    stats = collect_stats(db, hours)
    from app.llm.client import chat_completion, llm_provider_name

    narrative = chat_completion(
        system=(
            "You are a risk operations assistant. Summarize the merchant's last-24h risk posture "
            "in under 120 words for a dashboard digest. Mention action mix, notable rule hits and "
            "one concrete recommended follow-up. Plain text."
        ),
        user=str(stats),
    )
    source = f"llm:{llm_provider_name()}" if narrative else "stats"
    content = narrative.strip() if narrative else _fallback_digest(stats)

    digest = Digest(
        window_start=datetime.utcnow() - timedelta(hours=hours),
        window_end=datetime.utcnow(),
        content=content,
        source=source,
    )
    db.add(digest)
    db.commit()
    return {"id": digest.id, "content": content, "source": source, "stats": stats}


def _fallback_digest(stats: dict) -> str:
    by_action = stats.get("by_action", {})
    lines = [
        (
            f"Last {stats['window_hours']}h: {stats['total_transactions']} transactions processed "
            f"(avg latency {stats['avg_latency_ms']} ms)."
        ),
        (
            f"Actions - ALLOW {by_action.get('ALLOW', 0)}, REVIEW {by_action.get('REVIEW', 0)}, "
            f"BLOCK {by_action.get('BLOCK', 0)}, ESCALATED {by_action.get('ESCALATE', 0)}."
        ),
        (
            f"Blocked/escalated value: INR {stats['blocked_or_escalated_value_inr']:,.0f}; "
            f"review queue holds INR {stats['review_queue_value_inr']:,.0f}."
        ),
    ]
    rules = stats.get("top_rule_hits") or {}
    if rules:
        lines.append("Top rule signals: " + ", ".join(f"{k} x{v}" for k, v in list(rules.items())[:4]) + ".")
    else:
        lines.append("No velocity rules fired; traffic looks normal.")
    lines.append("Follow-up: clear pending REVIEW items to release legitimate customer funds faster.")
    return "\n".join(lines)
