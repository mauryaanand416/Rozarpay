import numpy as np
import pandas as pd

METHODS = np.array(["card", "upi", "netbanking", "wallet"])
METHOD_P = np.array([0.33, 0.47, 0.12, 0.08])
CHANNELS = np.array(["web", "android", "ios", "api"])
HOUR_P = np.array([1, 0.6, 0.4, 0.3, 0.3, 0.5, 1.5, 3, 5, 7, 8, 8, 8, 8, 8, 8, 9, 9, 8, 7, 6, 4, 2.5, 1.5])
HOUR_P = HOUR_P / HOUR_P.sum()
FOREIGN = ["US", "GB", "SG", "AE", "DE"]

AMOUNT_PARAMS = {
    "card": (7.7, 1.05),
    "upi": (6.1, 1.0),
    "netbanking": (8.4, 0.9),
    "wallet": (5.7, 0.85),
}


def _sample_amount(rng, method: str) -> float:
    mu, sigma = AMOUNT_PARAMS[method]
    return round(float(np.clip(rng.lognormal(mu, sigma), 10, 200_000)), 2)


def _customer_devices(rng, customer_ids) -> dict[str, list[str]]:
    return {
        c: [f"DEV-{c}-{i}" for i in range(rng.integers(1, 3))]
        for c in customer_ids
    }


def generate_transactions(n_normal: int = 110_000, seed: int = 42,
                          days: int = 90) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    end = pd.Timestamp.now().floor("h")
    start = end - pd.Timedelta(days=days)

    n_customers = 4000
    n_merchants = 160
    customer_ids = np.array([f"CUST{i:05d}" for i in range(n_customers)])
    merchant_ids = np.array([f"MERC{i:04d}" for i in range(n_merchants)])
    cust_devices = _customer_devices(rng, customer_ids)

    cust_weights = rng.pareto(1.4, n_customers) + 0.2
    merch_weights = rng.pareto(1.2, n_merchants) + 0.3
    foreign_mask = rng.random(n_customers) < 0.06
    foreign_country = np.array(rng.choice(FOREIGN, n_customers))

    span_ns = int((end - start).value)
    span_seconds = span_ns / 1_000_000_000
    offsets = (rng.random(n_normal) ** 1.05 * span_ns).astype(np.int64)
    base_times = (start.value + offsets).astype("datetime64[ns]")

    methods = rng.choice(METHODS, n_normal, p=METHOD_P)
    amounts = np.array([_sample_amount(rng, m) for m in methods])

    rebalanced_hours = rng.choice(24, n_normal, p=HOUR_P)
    adjusted = base_times.astype("datetime64[D]") + rebalanced_hours.astype("timedelta64[h]")
    jitter_min = rng.integers(0, 60, n_normal).astype("timedelta64[m]")
    times = adjusted + jitter_min

    rows = pd.DataFrame(
        {
            "txn_id": [f"TXN{i:07d}" for i in range(n_normal)],
            "event_time": times,
            "amount": amounts,
            "currency": "INR",
            "customer_id": rng.choice(customer_ids, n_normal, p=cust_weights / cust_weights.sum()),
            "merchant_id": rng.choice(merchant_ids, n_normal, p=merch_weights / merch_weights.sum()),
            "payment_method": methods,
            "device_id": "",
            "ip_country": "IN",
            "billing_country": "IN",
            "cvv_match": rng.random(n_normal) < 0.97,
            "avs_match": rng.random(n_normal) < 0.95,
            "card_age_days": rng.integers(30, 2200, n_normal),
            "channel": rng.choice(CHANNELS, n_normal, p=[0.45, 0.32, 0.18, 0.05]),
            "is_fraud": False,
        }
    )

    dev_pick = np.array([cust_devices[c][rng.integers(len(cust_devices[c]))] for c in rows["customer_id"]])
    rows["device_id"] = dev_pick

    cust_is_foreign = foreign_mask[np.searchsorted(customer_ids, rows["customer_id"])]
    travel = cust_is_foreign & (rng.random(n_normal) < 0.5)
    rows.loc[travel, "ip_country"] = foreign_country[np.searchsorted(customer_ids, rows["customer_id"][travel])]

    fraud_frames = []

    def new_device(customer: str) -> str:
        return f"DEV-NEW-{customer}-{rng.integers(100000)}"

    def make_rows(count: int, **overrides) -> pd.DataFrame:
        template = rows.iloc[rng.integers(0, len(rows), count)].copy()
        template["txn_id"] = [f"FRD{rng.integers(10**9):09d}{i}" for i in range(count)]
        for k, v in overrides.items():
            template[k] = v
        return template

    for _ in range(70):
        victim = str(rng.choice(customer_ids))
        burst_n = int(rng.integers(5, 11))
        t0 = start + pd.Timedelta(seconds=float(rng.random() * span_seconds))
        small_amounts = [round(float(rng.uniform(40, 199)), 2) for _ in range(burst_n)]
        big_amount = round(float(rng.uniform(12_000, 55_000)), 2)
        times_burst = [t0 + pd.Timedelta(minutes=float(m)) for m in sorted(rng.uniform(0.2, 14, burst_n))]
        times_burst.append(times_burst[-1] + pd.Timedelta(minutes=float(rng.uniform(3, 40))))

        stealth = rng.random() < 0.30
        frame = make_rows(
            burst_n + 1,
            customer_id=victim,
            amount=small_amounts + [big_amount],
            event_time=times_burst,
            payment_method="card",
            device_id=cust_devices[victim][0] if stealth else new_device(victim),
            ip_country="IN" if stealth else rng.choice(["US", "GB", "AE"]) if rng.random() < 0.8 else "IN",
            billing_country="IN",
            cvv_match=bool(rng.random() < (0.95 if stealth else 0.5)),
            avs_match=bool(rng.random() < (0.85 if stealth else 0.05)),
            card_age_days=int(rng.integers(60, 1800)),
            channel="web",
            is_fraud=True,
        )
        fraud_frames.append(frame)

    for _ in range(90):
        victim = str(rng.choice(customer_ids))
        seq_n = int(rng.integers(3, 7))
        t0 = start + pd.Timedelta(seconds=float(rng.random() * span_seconds))
        amounts_seq = [round(float(rng.uniform(4_000, 70_000)), 2) for _ in range(seq_n)]
        times_seq = [t0 + pd.Timedelta(minutes=float(m)) for m in sorted(rng.uniform(5, 360, seq_n))]

        stealth = rng.random() < 0.25
        frame = make_rows(
            seq_n,
            customer_id=victim,
            amount=amounts_seq,
            event_time=times_seq,
            payment_method=str(rng.choice(["netbanking", "card"])),
            device_id=cust_devices[victim][0] if stealth else new_device(victim),
            ip_country="IN" if stealth else str(rng.choice(FOREIGN)),
            billing_country="IN",
            cvv_match=True,
            avs_match=bool(rng.random() < (0.9 if stealth else 0.4)),
            card_age_days=int(rng.integers(120, 2200)),
            channel="api" if rng.random() < 0.5 else "android",
            is_fraud=True,
        )
        fraud_frames.append(frame)

    for _ in range(130):
        victim = str(rng.choice(customer_ids))
        t0 = start + pd.Timedelta(seconds=float(rng.random() * span_seconds))
        frame = make_rows(
            1,
            customer_id=victim,
            amount=[round(float(rng.uniform(20_000, 90_000)), 2)],
            event_time=[t0],
            payment_method="card",
            device_id=new_device(victim),
            ip_country="IN",
            billing_country="IN",
            cvv_match=True,
            avs_match=True,
            card_age_days=int(rng.integers(0, 2)),
            channel=str(rng.choice(["web", "android"])),
            is_fraud=True,
        )
        fraud_frames.append(frame)

    hard_negatives = []

    travelers = 1500
    t_travel = [start + pd.Timedelta(seconds=float(rng.random() * span_seconds)) for _ in range(travelers)]
    travel_customers = [str(rng.choice(customer_ids)) for _ in range(travelers)]
    hard_negatives.append(
        make_rows(
            travelers,
            customer_id=travel_customers,
            amount=[round(float(rng.uniform(5_000, 80_000)), 2) for _ in range(travelers)],
            event_time=t_travel,
            payment_method=str(rng.choice(["card", "netbanking"])),
            device_id=[cust_devices[c][rng.integers(len(cust_devices[c]))] for c in travel_customers],
            ip_country=rng.choice(FOREIGN, travelers),
            billing_country="IN",
            cvv_match=True,
            avs_match=True,
            card_age_days=[int(x) for x in rng.integers(200, 2200, travelers)],
            channel=str(rng.choice(["web", "android", "ios"])),
            is_fraud=False,
        )
    )

    n_new_card = 450
    nc_customers = [str(rng.choice(customer_ids)) for _ in range(n_new_card)]
    hard_negatives.append(
        make_rows(
            n_new_card,
            customer_id=nc_customers,
            amount=[round(float(rng.uniform(20_000, 90_000)), 2) for _ in range(n_new_card)],
            event_time=[start + pd.Timedelta(seconds=float(rng.random() * span_seconds)) for _ in range(n_new_card)],
            payment_method="card",
            device_id=[cust_devices[c][0] for c in nc_customers],
            ip_country="IN",
            billing_country="IN",
            cvv_match=True,
            avs_match=True,
            card_age_days=[int(x) for x in rng.integers(0, 2, n_new_card)],
            channel="web",
            is_fraud=False,
        )
    )

    n_night = 700
    night_times = []
    for _ in range(n_night):
        t = start + pd.Timedelta(seconds=float(rng.random() * span_seconds))
        night_times.append(t.floor("D") + pd.Timedelta(hours=int(rng.integers(0, 5)), minutes=int(rng.integers(60))))
    hard_negatives.append(
        make_rows(
            n_night,
            customer_id=[str(rng.choice(customer_ids)) for _ in range(n_night)],
            amount=[round(float(rng.uniform(25_000, 70_000)), 2) for _ in range(n_night)],
            event_time=night_times,
            payment_method="card",
            device_id=[
                cust_devices[str(rng.choice(customer_ids))][0]
                for _ in range(n_night)
            ],
            ip_country="IN",
            billing_country="IN",
            cvv_match=True,
            avs_match=True,
            card_age_days=[int(x) for x in rng.integers(100, 2200, n_night)],
            channel="android",
            is_fraud=False,
        )
    )

    for _ in range(350):
        victim = str(rng.choice(customer_ids))
        burst_n = int(rng.integers(6, 9))
        t0 = start + pd.Timedelta(seconds=float(rng.random() * span_seconds))
        times_burst = [t0 + pd.Timedelta(minutes=float(m)) for m in sorted(rng.uniform(1, 40, burst_n))]
        hard_negatives.append(
            make_rows(
                burst_n,
                customer_id=victim,
                amount=[round(float(rng.uniform(30, 180)), 2) for _ in range(burst_n)],
                event_time=times_burst,
                payment_method="upi",
                device_id=cust_devices[victim][rng.integers(len(cust_devices[victim]))],
                ip_country="IN",
                billing_country="IN",
                cvv_match=True,
                avs_match=True,
                card_age_days=int(rng.integers(100, 2200)),
                channel="android",
                is_fraud=False,
            )
        )

    df = pd.concat([rows] + hard_negatives + fraud_frames, ignore_index=True)
    df = df.sort_values("event_time").reset_index(drop=True)
    df["txn_id"] = [f"TXN{i:07d}" for i in range(len(df))]
    return df


if __name__ == "__main__":
    out_dir = __import__("pathlib").Path(__file__).resolve().parents[1] / "data"
    out_dir.mkdir(exist_ok=True)
    frame = generate_transactions()
    path = out_dir / "transactions.csv"
    frame.to_csv(path, index=False)
    print(f"wrote {len(frame)} rows ({frame['is_fraud'].sum()} fraud, {frame['is_fraud'].mean():.2%}) -> {path}")

