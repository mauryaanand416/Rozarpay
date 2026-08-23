
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import require_api_key
from app.db.base import get_db
from app.db.models import Decision, Transaction
from app.services.pipeline import process_transaction, serialize_decision

router = APIRouter(prefix="/api/v1/transactions", tags=["transactions"])


class TransactionIn(dict):
    pass


@router.post("", dependencies=[Depends(require_api_key)])
def score_transaction(txn: dict, db: Session = Depends(get_db)):
    required = ["amount", "customer_id", "merchant_id"]
    missing = [k for k in required if k not in txn]
    if missing:
        raise HTTPException(status_code=422, detail=f"missing fields: {missing}")
    try:
        float(txn["amount"])
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="amount must be numeric") from exc
    return process_transaction(db, txn)


@router.get("/recent", dependencies=[Depends(require_api_key)])
def recent(limit: int = Query(50, le=200), db: Session = Depends(get_db)):
    decisions = (
        db.query(Decision)
        .order_by(Decision.id.desc())
        .limit(limit)
        .all()
    )
    refs = [d.txn_ref for d in decisions]
    txns = {t.txn_ref: t for t in db.query(Transaction).filter(Transaction.txn_ref.in_(refs)).all()}
    out = []
    for d in decisions:
        item = serialize_decision(d, txns.get(d.txn_ref))
        item.pop("features", None)
        out.append(item)
    return {"items": out}


@router.get("/{decision_id}", dependencies=[Depends(require_api_key)])
def get_decision(decision_id: int, db: Session = Depends(get_db)):
    decision = db.query(Decision).filter(Decision.id == decision_id).first()
    if decision is None:
        raise HTTPException(status_code=404, detail="decision not found")
    txn = db.query(Transaction).filter(Transaction.txn_ref == decision.txn_ref).first()
    payload = serialize_decision(decision, txn)
    payload["features"] = decision.features
    return payload
