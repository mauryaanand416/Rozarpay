from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_api_key
from app.audit import ledger
from app.db.base import get_db
from app.db.models import AuditEntry

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


@router.get("", dependencies=[Depends(require_api_key)])
def audit_log(limit: int = Query(100, le=500), db: Session = Depends(get_db)):
    entries = db.query(AuditEntry).order_by(AuditEntry.seq.desc()).limit(limit).all()
    return {
        "items": [
            {
                "seq": e.seq,
                "decision_id": e.decision_id,
                "actor": e.actor,
                "action_type": e.action_type,
                "payload": e.payload,
                "prev_hash": e.prev_hash[:16],
                "entry_hash": e.entry_hash[:16],
                "created_at": e.created_at.isoformat(),
            }
            for e in entries
        ]
    }


@router.get("/verify", dependencies=[Depends(require_api_key)])
def verify(db: Session = Depends(get_db)):
    return ledger.verify_chain(db)
