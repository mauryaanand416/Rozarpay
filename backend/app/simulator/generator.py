import random
import threading
import uuid
from datetime import datetime, timedelta

from app.db.base import new_session
from app.services.pipeline import process_transaction

CUSTOMER_POOL = [f"CUST{i:05d}" for i in range(4000)]
MERCHANT_POOL = [f"MERC{i:04d}" for i in range(160)]
METHODS = ["card", "upi", "netbanking", "wallet"]
CHANNELS = ["web", "android", "ios", "api"]
COUNTRIES = ["IN", "IN", "IN", "IN", "IN", "IN", "IN", "US", "GB", "SG"]


def _now():
    return datetime.utcnow()


def normal_txn() -> dict:
    customer = random.choice(CUSTOMER_POOL)
    return {
        "txn_ref": f"SIM-{uuid.uuid4().hex[:10].upper()}",
        "event_time": _now(),
        "amount": round(random.lognormvariate(random.choice([6.2, 7.7, 8.3]), 1.0), 2),
        "customer_id": customer,
        "merchant_id": random.choice(MERCHANT_POOL),
        "payment_method": random.choices(METHODS, weights=[33, 47, 12, 8])[0],
        "device_id": f"DEV-{customer}-0",
        "ip_country": random.choice(COUNTRIES),
        "billing_country": "IN",
        "cvv_match": random.random() < 0.97,
        "avs_match": random.random() < 0.95,
        "card_age_days": random.randint(30, 2200),
        "channel": random.choices(CHANNELS, weights=[45, 32, 18, 5])[0],
    }


def card_testing_burst() -> list[dict]:
    victim = random.choice(CUSTOMER_POOL)
    device = f"DEV-NEW-{uuid.uuid4().hex[:8]}"
    n = random.randint(6, 9)
    txns = []
    t = _now()
    for _ in range(n):
        t = t + timedelta(seconds=random.randint(20, 90))
        txns.append(
            {
                "txn_ref": f"SIM-{uuid.uuid4().hex[:10].upper()}",
                "event_time": t,
                "amount": round(random.uniform(40, 199), 2),
                "customer_id": victim,
                "merchant_id": random.choice(MERCHANT_POOL),
                "payment_method": "card",
                "device_id": device,
                "ip_country": random.choice(["US", "AE", "IN"]),
                "billing_country": "IN",
                "cvv_match": random.random() < 0.5,
                "avs_match": False,
                "card_age_days": random.randint(60, 1800),
                "channel": "web",
            }
        )
    big = dict(txns[-1])
    big["amount"] = round(random.uniform(12_000, 55_000), 2)
    big["event_time"] = t + timedelta(minutes=random.randint(3, 25))
    big["txn_ref"] = f"SIM-{uuid.uuid4().hex[:10].upper()}"
    txns.append(big)
    return txns


def account_takeover() -> list[dict]:
    victim = random.choice(CUSTOMER_POOL)
    device = f"DEV-NEW-{uuid.uuid4().hex[:8]}"
    n = random.randint(3, 5)
    txns = []
    t = _now()
    for _ in range(n):
        t = t + timedelta(minutes=random.randint(4, 40))
        txns.append(
            {
                "txn_ref": f"SIM-{uuid.uuid4().hex[:10].upper()}",
                "event_time": t,
                "amount": round(random.uniform(4_000, 70_000), 2),
                "customer_id": victim,
                "merchant_id": random.choice(MERCHANT_POOL),
                "payment_method": random.choice(["netbanking", "card"]),
                "device_id": device,
                "ip_country": random.choice(["US", "GB", "SG"]),
                "billing_country": "IN",
                "cvv_match": True,
                "avs_match": False,
                "card_age_days": random.randint(120, 2200),
                "channel": "api",
            }
        )
    return txns


class Simulator:
    def __init__(self):
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._count = 0
        self._lock = threading.Lock()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def processed(self) -> int:
        return self._count

    def start(self) -> bool:
        with self._lock:
            if self.running:
                return False
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, daemon=True, name="simulator")
            self._thread.start()
            return True

    def stop(self) -> bool:
        with self._lock:
            if not self.running:
                return False
            self._stop.set()
            return True

    def _run(self):
        from app.config import get_settings

        settings = get_settings()
        while not self._stop.is_set():
            batch = [normal_txn()]
            self._count += 1
            if self._count % max(settings.simulator_attack_every, 3) == 0:
                scenario = card_testing_burst() if random.random() < 0.55 else account_takeover()
                batch.extend(scenario)

            for txn in batch:
                db = new_session()
                try:
                    process_transaction(db, txn)
                except Exception:
                    db.rollback()
                finally:
                    db.close()

            self._stop.wait(settings.simulator_interval_seconds)


simulator = Simulator()
