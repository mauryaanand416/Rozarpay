import threading

import joblib
import numpy as np
import pandas as pd

from app.config import get_settings
from app.ml.features import FEATURE_NAMES

FEATURE_LABELS = {
    "amount": "Transaction amount",
    "log_amount": "Transaction amount (log scale)",
    "hour_sin": "Time of day",
    "hour_cos": "Time of day",
    "day_of_week": "Day of week",
    "is_night": "Night-time transaction (00:00-05:00)",
    "cvv_match": "CVV verification result",
    "avs_match": "Address verification result",
    "card_age_days": "Card age",
    "country_mismatch": "IP country differs from billing country",
    "cust_txn_count_1h": "Customer transactions in last hour",
    "cust_txn_count_24h": "Customer transactions in last 24h",
    "cust_amount_sum_24h": "Customer spend in last 24h",
    "cust_max_amount_24h": "Largest customer txn in 24h",
    "cust_avg_amount_30d": "Customer average spend (30 days)",
    "device_txn_count_7d": "Device activity (7 days)",
    "merchant_txn_count_1h": "Merchant volume spike (last hour)",
    "prior_fraud_count_customer": "Prior confirmed fraud on this customer account",
    "amount_to_cust_avg_ratio": "Amount vs customer's normal spend",
    "payment_method": "Payment method",
    "channel": "Transaction channel",
}

_registry = None
_lock = threading.Lock()


class ModelRegistry:
    def __init__(self):
        settings = get_settings()
        self.settings = settings
        self.model = None
        self.feature_names: list[str] = FEATURE_NAMES
        self.cat_mappings: dict = {}
        self.available = False
        self.version = "none"
        self.load_error: str | None = None
        try:
            self.reload()
        except Exception as exc:
            self.load_error = str(exc)

    def reload(self):
        artifacts = self.settings.artifacts_dir
        self.model = joblib.load(artifacts / "model.joblib")
        meta_joblib = artifacts / "features_meta.json"
        import json

        meta = json.loads(meta_joblib.read_text()) if meta_joblib.exists() else {}
        self.feature_names = meta.get("feature_names", FEATURE_NAMES)
        self.cat_mappings = meta.get("categorical_mappings", {})
        metrics_path = artifacts / "metrics.json"
        if metrics_path.exists():
            self.version = json.loads(metrics_path.read_text()).get("model_version", "unknown")
        self.available = True
        self.load_error = None

    def encode(self, feats: dict) -> pd.DataFrame:
        import pandas as pd

        data = {}
        for name in self.feature_names:
            value = feats.get(name)
            if name in self.cat_mappings:
                mapping = self.cat_mappings[name]
                categories = sorted(mapping.keys(), key=lambda k: mapping[k])
                data[name] = pd.Categorical(
                    [str(value) if value is not None else None], categories=categories
                )
            else:
                data[name] = [float(value) if value is not None else 0.0]
        return pd.DataFrame(data, columns=self.feature_names)

    def score(self, feats: dict) -> float:
        if not self.available:
            raise RuntimeError("model not available")
        X = self.encode(feats)
        return float(self.model.predict_proba(X)[0, 1])

    def top_reasons(self, feats: dict, k: int = 3) -> list[dict]:
        if not self.available:
            return []
        try:
            import shap

            X = self.encode(feats)
            if getattr(self, "_explainer", None) is None or getattr(self, "_explainer_version", "") != self.version:
                self._explainer = shap.TreeExplainer(self.model)
                self._explainer_version = self.version
            sv = self._explainer.shap_values(X)
            if isinstance(sv, list):
                sv = sv[1] if len(sv) > 1 else sv[0]
            contributions = np.asarray(sv)[0]
            order = np.argsort(-np.abs(contributions))[:k]
            return [
                {
                    "feature": self.feature_names[i],
                    "label": FEATURE_LABELS.get(self.feature_names[i], self.feature_names[i]),
                    "impact": round(float(contributions[i]), 4),
                    "value": feats.get(self.feature_names[i]),
                }
                for i in order
            ]
        except Exception:
            ranked = sorted(
                ((name, abs(float(feats.get(name, 0) or 0))) for name in self.feature_names),
                key=lambda kv: kv[1],
                reverse=True,
            )[:k]
            return [
                {
                    "feature": name,
                    "label": FEATURE_LABELS.get(name, name),
                    "impact": None,
                    "value": feats.get(name),
                }
                for name, _ in ranked
            ]


def get_registry() -> ModelRegistry:
    global _registry
    if _registry is None:
        with _lock:
            if _registry is None:
                _registry = ModelRegistry()
    return _registry
