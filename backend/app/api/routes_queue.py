from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import require_api_key
from app.db.base import get_db
from app.db.models import Decision, Review, Transaction
from app.services.pipeline import serialize_decision

router = APIRouter(prefix="/api/v1/queue", tags=["review-queue"])


@router.get("", dependencies=[Depends(require_api_key)])
def pending(limit: int = Query(50, le=200), db: Session = Depends(get_db)):
    reviews = (
        db.query(Review)
        .filter(Review.status == "pending")
        .order_by(Review.id.desc())
        .limit(limit)
        .all()
    )
    decision_ids = [r.decision_id for r in reviews]
    decisions = {
        d.id: d for d in db.query(Decision).filter(Decision.id.in_(decision_ids)).all()
    }
    txn_refs = [d.txn_ref for d in decisions.values()]
    txns = {t.txn_ref: t for t in db.query(Transaction).filter(Transaction.txn_ref.in_(txn_refs)).all()}

    items = []
    for r in reviews:
        d = decisions.get(r.decision_id)
        if d is None:
            continue
        payload = serialize_decision(d, txns.get(d.txn_ref))
        payload["review"] = {"id": r.id, "status": r.status, "created_at": r.created_at.isoformat()}
        items.append(payload)

    items.sort(key=lambda x: x.get("risk_score") or 0, reverse=True)
    return {"items": items, "pending_count": len(items)}


@router.post("/{review_id}/resolve", dependencies=[Depends(require_api_key)])
def resolve(review_id: int, body: dict, db: Session = Depends(get_db)):
    from app.audit import ledger
    from app.llm.client import chat_completion

    review = db.query(Review).filter(Review.id == review_id).first()
    if review is None:
        raise HTTPException(status_code=404, detail="review not found")
    if review.status != "pending":
        raise HTTPException(status_code=409, detail="review already resolved")

    outcome = str(body.get("outcome", "")).lower()
    if outcome not in ("fraud", "legitimate"):
        raise HTTPException(status_code=422, detail='outcome must be "fraud" or "legitimate"')

    analyst = str(body.get("analyst", "analyst"))[:60]
    notes = str(body.get("notes", ""))[:2000]
    label = outcome == "fraud"

    review.status = "resolved"
    review.outcome_label = label
    review.analyst = analyst
    review.notes = notes or None
    review.resolved_at = __import__("datetime").datetime.utcnow()

    decision = db.query(Decision).filter(Decision.id == review.decision_id).first()
    if decision is not None:
        txn = db.query(Transaction).filter(Transaction.txn_ref == decision.txn_ref).first()
        if txn is not None:
            txn.is_fraud = label

    ledger.append_entry(
        db,
        actor=f"analyst:{analyst}",
        action_type="review:resolved",
        payload={"review_id": review.id, "outcome": outcome, "notes": notes[:300]},
        decision_id=review.decision_id,
    )

    suggestion = None
    if decision is not None:
        suggestion = chat_completion(
            system=(
                "You assist a payments risk analyst. Given the analyst's resolution of a flagged "
                "transaction, write 1-2 sentences of follow-up guidance (e.g., customer outreach, "
                "card reissue, watchlist update). Plain text only."
            ),
            user=(
                f"Transaction {review.txn_ref}, action was {decision.action}, "
                f"analyst verdict: {outcome}. Notes: {notes or 'none'}"
            ),
        )

    db.commit()

    from app.services.bus import bus

    bus.publish({"type": "queue_update"})

    return {"status": "resolved", "outcome": outcome, "label_recorded": label, "suggested_followup": suggestion}
