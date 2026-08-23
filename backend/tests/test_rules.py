from app.engine.rules import ALLOW, BLOCK, ESCALATE, REVIEW, evaluate_rules, max_action


def _feats(**overrides):
    base = {
        "amount": 1000.0,
        "cust_txn_count_1h": 1,
        "cust_txn_count_24h": 2,
        "cust_amount_sum_24h": 2000.0,
        "country_mismatch": 0.0,
        "is_night": 0.0,
        "card_age_days": 500,
        "device_txn_count_7d": 3,
    }
    base.update(overrides)
    return base


def _txn(amount=1000.0):
    return {"amount": amount, "customer_id": "C1", "merchant_id": "M1", "device_id": "D1"}


def test_clean_transaction_has_no_rules():
    assert evaluate_rules(_feats(), _txn()) == []


def test_card_testing_burst_blocks():
    hits = evaluate_rules(_feats(cust_txn_count_1h=7), _txn(amount=80))
    codes = [h.code for h in hits]
    assert "CARD_TESTING_BURST" in codes
    hit = next(h for h in hits if h.code == "CARD_TESTING_BURST")
    assert hit.min_action == BLOCK


def test_geo_mismatch_high_value_reviews():
    txn = dict(_txn(amount=25000))
    hits = evaluate_rules(_feats(country_mismatch=1.0, amount=25000), txn)
    assert any(h.code == "GEO_MISMATCH_HIGH_VALUE" and h.min_action == REVIEW for h in hits)


def test_new_card_high_value_blocks():
    hits = evaluate_rules(_feats(card_age_days=1, amount=30000), _txn(amount=30000))
    assert any(h.code == "NEW_CARD_HIGH_VALUE" and h.min_action == BLOCK for h in hits)


def test_night_large_amount():
    hits = evaluate_rules(_feats(is_night=1.0, amount=40000), _txn(amount=40000))
    assert any(h.code == "NIGHT_LARGE_AMOUNT" and h.min_action == REVIEW for h in hits)


def test_device_farm_signal():
    hits = evaluate_rules(_feats(device_txn_count_7d=55), _txn())
    assert any(h.code == "DEVICE_FARM_SIGNAL" for h in hits)


def test_max_action_priority():
    assert max_action([ALLOW]) == ALLOW
    assert max_action([ALLOW, REVIEW]) == REVIEW
    assert max_action([REVIEW, BLOCK]) == BLOCK
    assert max_action([BLOCK, ESCALATE]) == ESCALATE
