import hashlib
import json

from sqlalchemy.orm import Session

from app.db.models import AuditEntry

GENESIS_HASH = "0" * 64


def _canonical(entry: dict) -> bytes:
    return json.dumps(entry, sort_keys=True, separators=(",", ":"), default=str).encode()


def append_entry(
    db: Session,
    *,
    actor: str,
    action_type: str,
    payload: dict,
    decision_id: int | None = None,
) -> AuditEntry:
    last = db.query(AuditEntry).order_by(AuditEntry.seq.desc()).first()
    seq = (last.seq + 1) if last else 1
    prev_hash = last.entry_hash if last else GENESIS_HASH

    body = {
        "seq": seq,
        "decision_id": decision_id,
        "actor": actor,
        "action_type": action_type,
        "payload": payload,
        "prev_hash": prev_hash,
    }
    entry_hash = hashlib.sha256(_canonical(body)).hexdigest()

    entry = AuditEntry(
        seq=seq,
        decision_id=decision_id,
        actor=actor,
        action_type=action_type,
        payload=payload,
        prev_hash=prev_hash,
        entry_hash=entry_hash,
    )
    db.add(entry)
    db.flush()
    return entry


def verify_chain(db: Session) -> dict:
    entries = db.query(AuditEntry).order_by(AuditEntry.seq.asc()).all()
    expected_prev = GENESIS_HASH
    for i, e in enumerate(entries):
        if e.seq != i + 1:
            return {"valid": False, "broken_at_seq": e.seq, "reason": "sequence gap"}
        if e.prev_hash != expected_prev:
            return {"valid": False, "broken_at_seq": e.seq, "reason": "prev_hash mismatch"}
        body = {
            "seq": e.seq,
            "decision_id": e.decision_id,
            "actor": e.actor,
            "action_type": e.action_type,
            "payload": e.payload,
            "prev_hash": e.prev_hash,
        }
        if hashlib.sha256(_canonical(body)).hexdigest() != e.entry_hash:
            return {"valid": False, "broken_at_seq": e.seq, "reason": "entry tampered"}
        expected_prev = e.entry_hash
    return {"valid": True, "entries": len(entries), "head_hash": expected_prev}
