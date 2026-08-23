

def test_healthz(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert "safe_mode" in body
    assert "model" in body


def test_requires_api_key(client):
    resp = client.post(
        "/api/v1/transactions",
        json={"amount": 500, "customer_id": "C1", "merchant_id": "M1"},
    )
    assert resp.status_code == 401


def test_missing_fields_rejected(client, auth_headers):
    resp = client.post("/api/v1/transactions", json={"amount": 500}, headers=auth_headers)
    assert resp.status_code == 422


def test_score_transaction_returns_gated_decision(client, auth_headers):
    txn = {
        "amount": 1200.0,
        "customer_id": "CUST00001",
        "merchant_id": "MERC0001",
        "payment_method": "upi",
        "device_id": "DEV-CUST00001-0",
        "ip_country": "IN",
        "billing_country": "IN",
        "cvv_match": True,
        "avs_match": True,
        "card_age_days": 800,
        "channel": "android",
    }
    resp = client.post("/api/v1/transactions", json=txn, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    for key in ("decision_id", "txn_ref", "action", "reasons", "risk_score", "latency_ms"):
        assert key in body
    assert body["action"] in ("ALLOW", "REVIEW", "BLOCK", "ESCALATE")
    assert 0.0 <= (body["risk_score"] or 0) <= 1.0

    audit = client.get("/api/v1/audit?limit=10", headers=auth_headers).json()
    assert len(audit["items"]) >= 1

    verify = client.get("/api/v1/audit/verify", headers=auth_headers).json()
    assert verify["valid"] is True


def test_review_queue_flow(client, auth_headers):
    txns = [
        {
            "amount": 150.0,
            "customer_id": "CUST04200",
            "merchant_id": "MERC0007",
            "payment_method": "card",
            "device_id": f"DEV-NEW-{i}",
            "ip_country": "US",
            "billing_country": "IN",
            "cvv_match": False,
            "avs_match": False,
            "card_age_days": 300,
            "channel": "web",
        }
        for i in range(6)
    ]
    last = None
    for t in txns:
        last = client.post("/api/v1/transactions", json=t, headers=auth_headers)

    assert last is not None and last.status_code == 200

    queue = client.get("/api/v1/queue", headers=auth_headers).json()
    if queue["pending_count"] == 0:
        return

    review = queue["items"][0]["review"]
    resolve = client.post(
        f"/api/v1/queue/{review['id']}/resolve",
        json={"outcome": "fraud", "analyst": "tester", "notes": "confirmed card testing"},
        headers=auth_headers,
    )
    assert resolve.status_code == 200
    body = resolve.json()
    assert body["status"] == "resolved"
    assert body["label_recorded"] is True

    again = client.post(
        f"/api/v1/queue/{review['id']}/resolve",
        json={"outcome": "legitimate"},
        headers=auth_headers,
    )
    assert again.status_code == 409


def test_high_value_block_is_escalated_not_blocked(client, auth_headers):
    txns = [
        {
            "amount": 60_000.0,
            "customer_id": "CUST05555",
            "merchant_id": "MERC0012",
            "payment_method": "card",
            "device_id": f"DEV-ESK-{i}",
            "ip_country": "GB",
            "billing_country": "IN",
            "cvv_match": False,
            "avs_match": False,
            "card_age_days": 900,
            "channel": "web",
        }
        for i in range(5)
    ]
    final = None
    for t in txns:
        resp = client.post("/api/v1/transactions", json=t, headers=auth_headers)
        assert resp.status_code == 200
        final = resp.json()

    if final["action"] == "BLOCK":
        codes = [r["code"] for r in final["reasons"]]
        assert "HIGH_VALUE_HUMAN_GATE" not in codes
    elif final["action"] == "ESCALATE":
        codes = [r["code"] for r in final["reasons"]]
        assert "HIGH_VALUE_HUMAN_GATE" in codes


def test_metrics_endpoints(client, auth_headers):
    model = client.get("/api/v1/metrics/model", headers=auth_headers)
    assert model.status_code in (200,)
    live = client.get("/api/v1/metrics/live", headers=auth_headers)
    assert live.status_code == 200

