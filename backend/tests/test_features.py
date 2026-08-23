import pandas as pd

from app.ml.features import (
    FEATURE_NAMES,
    build_online_features,
    build_training_features,
)


def _make_df(n_customers=6, per_customer=40):
    rows = []
    base = pd.Timestamp("2026-07-01 10:00")
    for c in range(n_customers):
        t = base
        for i in range(per_customer):
            t = t + pd.Timedelta(hours=float(3 + (i % 5)))
            rows.append(
                {
                    "txn_id": f"T{c}-{i}",
                    "event_time": t,
                    "amount": 100 + (i * 37 % 900) + c,
                    "currency": "INR",
                    "customer_id": f"C{c:03d}",
                    "merchant_id": f"M{c % 3:02d}",
                    "payment_method": "upi" if i % 2 else "card",
                    "device_id": f"D{c:03d}",
                    "ip_country": "IN",
                    "billing_country": "IN",
                    "cvv_match": True,
                    "avs_match": True,
                    "card_age_days": 400,
                    "channel": "web",
                    "is_fraud": False,
                }
            )
    return pd.DataFrame(rows)


def test_training_features_shape_and_names():
    df = _make_df()
    features, labels = build_training_features(df, progress_every=0)
    assert list(features.columns) == FEATURE_NAMES
    assert len(features) == len(df)
    assert len(labels) == len(df)


def test_online_matches_training_semantics():
    dfs = _make_df().sort_values("event_time").reset_index(drop=True)
    features, _ = build_training_features(dfs, progress_every=0)

    probe_idx = 30
    row = dfs.iloc[probe_idx]
    past = dfs.iloc[:probe_idx]
    online = build_online_features(row.to_dict(), past)

    assert abs(features.iloc[probe_idx]["cust_txn_count_24h"] - online["cust_txn_count_24h"]) <= 1
    assert abs(features.iloc[probe_idx]["cust_amount_sum_24h"] - online["cust_amount_sum_24h"]) < 1e-6


def test_velocity_counts_increase_with_burst():
    df = _make_df()
    burst_time = df["event_time"].max() + pd.Timedelta(minutes=10)
    burst_rows = [
        {
            "txn_id": f"B{i}",
            "event_time": burst_time + pd.Timedelta(minutes=i),
            "amount": 50.0,
            "customer_id": "C000",
            "merchant_id": "M00",
            "device_id": "DNEW",
            "ip_country": "US",
            "billing_country": "IN",
            "cvv_match": False,
            "avs_match": False,
            "card_age_days": 500,
            "channel": "web",
            "is_fraud": True,
        }
        for i in range(7)
    ]
    df2 = pd.concat([df, pd.DataFrame(burst_rows)], ignore_index=True)
    feats, _ = build_training_features(df2, progress_every=0)
    last = feats.iloc[-1]
    assert last["cust_txn_count_1h"] >= 6
