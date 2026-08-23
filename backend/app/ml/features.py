import numpy as np
import pandas as pd

CATEGORICAL_FEATURES = ["payment_method", "channel"]
FEATURE_NAMES = [
    "amount",
    "log_amount",
    "hour_sin",
    "hour_cos",
    "day_of_week",
    "is_night",
    "cvv_match",
    "avs_match",
    "card_age_days",
    "country_mismatch",
    "cust_txn_count_1h",
    "cust_txn_count_24h",
    "cust_amount_sum_24h",
    "cust_max_amount_24h",
    "cust_avg_amount_30d",
    "device_txn_count_7d",
    "merchant_txn_count_1h",
    "prior_fraud_count_customer",
    "amount_to_cust_avg_ratio",
    "payment_method",
    "channel",
]

HOUR_NS = 3600 * 1_000_000_000
DAY_NS = 24 * HOUR_NS
WEEK_NS = 7 * DAY_NS
MONTH_NS = 30 * DAY_NS


def base_static(txn: dict) -> dict:
    amount = float(txn.get("amount", 0.0))
    ts = pd.Timestamp(txn.get("event_time"))
    if ts.tzinfo is not None:
        ts = ts.tz_localize(None)
    hour = ts.hour + ts.minute / 60.0
    ip_country = str(txn.get("ip_country", "")).upper()
    billing_country = str(txn.get("billing_country", "")).upper()
    return {
        "amount": amount,
        "log_amount": float(np.log1p(amount)),
        "hour_sin": float(np.sin(2 * np.pi * hour / 24)),
        "hour_cos": float(np.cos(2 * np.pi * hour / 24)),
        "day_of_week": float(ts.dayofweek),
        "is_night": float(0 <= ts.hour < 5),
        "cvv_match": float(bool(txn.get("cvv_match", True))),
        "avs_match": float(bool(txn.get("avs_match", True))),
        "card_age_days": float(txn.get("card_age_days", 365)),
        "country_mismatch": float(ip_country != billing_country),
        "payment_method": str(txn.get("payment_method", "card")),
        "channel": str(txn.get("channel", "web")),
    }


def _window_agg(times: np.ndarray, amounts: np.ndarray, now_ns: int,
                window_ns: int, prefix: np.ndarray | None = None) -> dict:
    lo = np.searchsorted(times, now_ns - window_ns, side="left")
    hi = np.searchsorted(times, now_ns, side="left")
    count = hi - lo
    result = {
        "count": count,
        "sum": float(prefix[hi] - prefix[lo]) if prefix is not None else 0.0,
        "max": float(amounts[lo:hi].max()) if count else 0.0,
    }
    return result


def build_online_features(txn: dict, history: pd.DataFrame) -> dict:
    feats = base_static(txn)
    ts = pd.Timestamp(txn.get("event_time"))
    if ts.tzinfo is not None:
        ts = ts.tz_localize(None)
    now_ns = int(ts.value)

    empty = np.empty(0, dtype=np.int64)
    amt_dtype = np.float64

    def entity_arrays(key_col: str, key_val):
        if not len(history):
            return empty, np.empty(0, dtype=amt_dtype), None
        sub = history[history[key_col] == key_val]
        if not len(sub):
            return empty, np.empty(0, dtype=amt_dtype), None
        times = pd.to_datetime(sub["event_time"]).values.astype("datetime64[ns]").astype(np.int64)
        amounts = sub["amount"].to_numpy(dtype=amt_dtype)
        order = np.argsort(times, kind="stable")
        return times[order], amounts[order], sub["is_fraud"].fillna(False).astype(bool).to_numpy()[order]

    cust_t, cust_a, cust_f = entity_arrays("customer_id", txn.get("customer_id"))
    dev_t, dev_a, _ = entity_arrays("device_id", txn.get("device_id"))
    mer_t, mer_a, _ = entity_arrays("merchant_id", txn.get("merchant_id"))

    cust_prefix = np.concatenate([[0.0], np.cumsum(cust_a)]) if len(cust_a) else None

    c1 = _window_agg(cust_t, cust_a, now_ns, HOUR_NS, cust_prefix)
    c24 = _window_agg(cust_t, cust_a, now_ns, DAY_NS, cust_prefix)
    c30 = _window_agg(cust_t, cust_a, now_ns, MONTH_NS, cust_prefix)
    d7 = _window_agg(dev_t, dev_a, now_ns, WEEK_NS)
    m1 = _window_agg(mer_t, mer_a, now_ns, HOUR_NS)

    fraud_hi = int(np.searchsorted(cust_t, now_ns, side="left")) if len(cust_t) else 0
    prior_fraud_count = int(cust_f[:fraud_hi].sum()) if cust_f is not None else 0

    avg30 = c30["sum"] / c30["count"] if c30["count"] else 0.0
    amount = feats["amount"]

    feats.update(
        {
            "cust_txn_count_1h": float(c1["count"]),
            "cust_txn_count_24h": float(c24["count"]),
            "cust_amount_sum_24h": c24["sum"],
            "cust_max_amount_24h": c24["max"],
            "cust_avg_amount_30d": float(avg30),
            "device_txn_count_7d": float(d7["count"]),
            "merchant_txn_count_1h": float(m1["count"]),
            "prior_fraud_count_customer": float(prior_fraud_count),
            "amount_to_cust_avg_ratio": float(amount / avg30) if avg30 > 0 else 1.0,
        }
    )
    return feats


def build_training_features(df: pd.DataFrame, progress_every: int = 25000) -> tuple[pd.DataFrame, list[int]]:
    df = df.copy()
    df["event_time"] = pd.to_datetime(df["event_time"])
    if df["event_time"].dt.tz is not None:
        df["event_time"] = df["event_time"].dt.tz_localize(None)
    df = df.sort_values("event_time").reset_index(drop=True)

    keys = {
        "customer_id": ("customer_id", True),
        "device_id": ("device_id", False),
        "merchant_id": ("merchant_id", False),
    }
    index_store: dict[str, dict] = {}
    for name, (col, track_fraud) in keys.items():
        index_store[name] = {}
        times_lists: dict = {}
        amt_lists: dict = {}
        fraud_lists: dict = {}
        cols = df[[col, "event_time", "amount"] + (["is_fraud"] if track_fraud else [])]
        arr_times = pd.to_datetime(cols["event_time"]).values.astype("datetime64[ns]").astype(np.int64)
        arr_amt = cols["amount"].to_numpy(dtype=np.float64)
        arr_key = cols[col].to_numpy()
        arr_fraud = (
            pd.Series(cols["is_fraud"]).fillna(False).astype(bool).to_numpy() if track_fraud else None
        )
        for i in range(len(df)):
            k = arr_key[i]
            lst = times_lists.setdefault(k, [])
            lst.append(arr_times[i])
            amt_lists.setdefault(k, []).append(arr_amt[i])
            if track_fraud:
                fraud_lists.setdefault(k, []).append(arr_fraud[i])
        for k in times_lists:
            t = np.asarray(times_lists[k], dtype=np.int64)
            a = np.asarray(amt_lists[k], dtype=np.float64)
            order = np.argsort(t, kind="stable")
            f = np.asarray(fraud_lists[k], dtype=bool)[order] if track_fraud else None
            index_store[name][k] = (t[order], a[order], f)

    rows = []
    labels = []
    n = len(df)
    col_key_customer = df["customer_id"].to_numpy()
    col_key_device = df["device_id"].to_numpy()
    col_key_merchant = df["merchant_id"].to_numpy()

    records = df.to_dict("records")
    event_times_ns = pd.to_datetime(df["event_time"]).values.astype("datetime64[ns]").astype(np.int64)
    static_rows = [base_static(records[i]) for i in range(n)]

    for i in range(n):
        now_ns = int(event_times_ns[i])
        ck = col_key_customer[i]

        ct, ca, cf = index_store["customer_id"][ck]
        pos_hi = int(np.searchsorted(ct, now_ns, side="left"))

        def agg(t, a, hi, window_ns, now=now_ns, want_max=False, prefix=None):
            lo = int(np.searchsorted(t, now - window_ns, side="left"))
            cnt = hi - lo
            s = float(prefix[hi] - prefix[lo]) if prefix is not None else 0.0
            mx = float(a[lo:hi].max()) if (want_max and cnt) else 0.0
            return cnt, s, mx

        cust_prefix_full = np.concatenate([[0.0], np.cumsum(ca)])
        c1_cnt, _, _ = agg(ct, ca, pos_hi, HOUR_NS)
        c24_cnt, c24_sum, c24_max = agg(ct, ca, pos_hi, DAY_NS, want_max=True, prefix=cust_prefix_full)
        c30_cnt, c30_sum, _ = agg(ct, ca, pos_hi, MONTH_NS)
        dt_, da_, _ = index_store["device_id"][col_key_device[i]]
        d7_cnt, _, _ = agg(dt_, da_, int(np.searchsorted(dt_, now_ns, side="left")), WEEK_NS)
        mt_, ma_, _ = index_store["merchant_id"][col_key_merchant[i]]
        m1_cnt, _, _ = agg(mt_, ma_, int(np.searchsorted(mt_, now_ns, side="left")), HOUR_NS)

        prior_fraud_count = int(cf[:pos_hi].sum())
        avg30 = c30_sum / c30_cnt if c30_cnt else 0.0

        feats = dict(static_rows[i])
        amount = feats["amount"]
        feats.update(
            {
                "cust_txn_count_1h": float(c1_cnt),
                "cust_txn_count_24h": float(c24_cnt),
                "cust_amount_sum_24h": c24_sum,
                "cust_max_amount_24h": c24_max,
                "cust_avg_amount_30d": float(avg30),
                "device_txn_count_7d": float(d7_cnt),
                "merchant_txn_count_1h": float(m1_cnt),
                "prior_fraud_count_customer": float(prior_fraud_count),
                "amount_to_cust_avg_ratio": float(amount / avg30) if avg30 > 0 else 1.0,
            }
        )
        rows.append(feats)
        labels.append(int(bool(df["is_fraud"].iloc[i])))
        if progress_every and (i + 1) % progress_every == 0:
            print(f"features: {i + 1}/{n}")

    features = pd.DataFrame(rows, columns=FEATURE_NAMES)
    for col in CATEGORICAL_FEATURES:
        features[col] = features[col].astype("category")
    return features, labels
