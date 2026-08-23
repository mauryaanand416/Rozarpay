from app.audit import ledger
from app.db.models import AuditEntry


def test_chain_links_and_verifies(fresh_db):
    db = fresh_db()
    try:
        before = db.query(AuditEntry).count()
        e1 = ledger.append_entry(db, actor="system", action_type="decision:block", payload={"a": 1})
        e2 = ledger.append_entry(db, actor="analyst:x", action_type="review:resolved", payload={"b": 2})
        db.commit()

        assert e1.seq == before + 1
        assert e1.prev_hash if before else e1.prev_hash == ledger.GENESIS_HASH
        assert e2.prev_hash == e1.entry_hash

        result = ledger.verify_chain(db)
        assert result["valid"] is True
        assert result["entries"] >= before + 2
    finally:
        db.close()


def test_tamper_detection(fresh_db):
    db = fresh_db()
    try:
        entry = ledger.append_entry(db, actor="system", action_type="decision:block", payload={"txn": "t2"})
        db.commit()
        seq = entry.seq

        victim = db.query(AuditEntry).filter(AuditEntry.seq == seq).first()
        victim.payload["txn"] = "TAMPERED"
        db.commit()

        result = ledger.verify_chain(db)
        assert result["valid"] is False
        assert result["broken_at_seq"] == seq
    finally:
        db.close()
