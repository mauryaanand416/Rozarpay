from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.models import Decision

_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="explain")


def queue_explanation(decision_id: int) -> None:
    _executor.submit(_explain_task, decision_id)


def _explain_task(decision_id: int) -> None:
    from app.db.base import new_session
    from app.db.models import Decision
    from app.llm.client import chat_completion, llm_provider_name
    from app.services.bus import bus

    db = new_session()
    try:
        decision = db.query(Decision).filter(Decision.id == decision_id).first()
        if decision is None:
            return

        explanation, source = _template_explanation(decision)
        llm_text = chat_completion(
            system=(
                "You are a payments risk analyst writing short internal explanations of fraud "
                "decisions. In at most 4 sentences, explain why this transaction got its action "
                "(ALLOW/REVIEW/BLOCK/ESCALATE). Reference the concrete signals given. Be factual, "
                "no speculation, no advice."
            ),
            user=_decision_context(decision),
        )
        if llm_text:
            explanation, source = llm_text.strip(), f"llm:{llm_provider_name()}"

        decision.explanation = explanation
        decision.explanation_source = source
        db.commit()

        bus.publish(
            {
                "type": "explanation",
                "decision_id": decision.id,
                "explanation": explanation,
                "explanation_source": source,
            }
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _decision_context(decision: Decision) -> str:
    txn = decision.features or {}
    signals = "\n".join(
        f"- [{r.get('source')}] {r.get('code')}: {r.get('description')}"
        for r in (decision.reasons or [])
        if r.get("source") in ("rule", "gate", "system")
    )
    return (
        f"Transaction {decision.txn_ref}\n"
        f"Amount: {txn.get('amount', 'unknown')} INR\n"
        f"Model risk score: {max(decision.risk_score, 0):.3f}\n"
        f"Action taken: {decision.action}\n"
        f"Signals:\n{signals or '- none beyond the model score'}"
    )


def _template_explanation(decision: Decision) -> tuple[str, str]:
    rule_reasons = [r for r in (decision.reasons or []) if r.get("source") in ("rule", "gate", "system")]
    parts = []
    if decision.action == "ALLOW":
        parts.append(f"Allowed automatically: risk score {max(decision.risk_score, 0):.2f} below review threshold.")
    elif decision.action == "REVIEW":
        parts.append(f"Held for manual review: risk score {max(decision.risk_score, 0):.2f} crossed the review threshold.")
    elif decision.action == "BLOCK":
        parts.append(f"Blocked automatically: risk score {max(decision.risk_score, 0):.2f} crossed the block threshold.")
    else:
        parts.append(
            f"Escalated to a human reviewer instead of auto-blocking because the amount exceeds the "
            f"configured hard gate, even though risk score was {max(decision.risk_score, 0):.2f}."
        )
    if rule_reasons:
        parts.append("Triggered rules: " + "; ".join(r["description"] for r in rule_reasons[:3]) + ".")
    return " ".join(parts), "template"
