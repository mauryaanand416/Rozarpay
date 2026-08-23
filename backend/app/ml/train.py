import json
from datetime import UTC, datetime

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss

from app.config import get_settings
from app.ml.evaluate import (
    choose_threshold_cost_based,
    classification_metrics,
    pr_auc,
    roc_auc,
    save_json,
)
from app.ml.features import CATEGORICAL_FEATURES, FEATURE_NAMES, build_training_features


def load_dataset() -> pd.DataFrame:
    settings = get_settings()
    path = settings.data_dir / "transactions.csv"
    if not path.exists():
        from app.ml.synthetic import generate_transactions

        settings.data_dir.mkdir(parents=True, exist_ok=True)
        df = generate_transactions()
        df.to_csv(path, index=False)
    df = pd.read_csv(path)
    df["event_time"] = pd.to_datetime(df["event_time"])
    return df


def encode_categoricals(features: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    mappings: dict[str, dict] = {}
    encoded = features.copy()
    for col in CATEGORICAL_FEATURES:
        cats = sorted(encoded[col].astype(str).unique().tolist())
        mapping = {c: i for i, c in enumerate(cats)}
        mappings[col] = mapping
        encoded[col] = encoded[col].astype(str).map(mapping).astype(int)
        encoded[col] = encoded[col].astype("category")
    return encoded, mappings


def pick_review_threshold(y_true, probs, recall_floor: float) -> float:
    y_true = np.asarray(y_true)
    best_t, best_f2 = 0.5, -1.0
    for t in np.quantile(probs, np.linspace(0.01, 0.99, 197)):
        preds = (probs >= t).astype(int)
        tp = ((preds == 1) & (y_true == 1)).sum()
        fp = ((preds == 1) & (y_true == 0)).sum()
        fn = ((preds == 0) & (y_true == 1)).sum()
        precision = tp / max(tp + fp, 1)
        recall = tp / max(tp + fn, 1)
        denom = (4 * precision + recall)
        f2 = 5 * precision * recall / denom if denom else 0.0
        if recall >= recall_floor and f2 > best_f2:
            best_f2, best_t = f2, float(t)
    return best_t


def pick_block_threshold(y_true, probs, min_recall: float = 0.5) -> float:
    y_true = np.asarray(y_true)
    best_t, best_precision = None, -1.0
    for t in np.quantile(probs, np.linspace(0.01, 0.999, 400)):
        preds = (probs >= t).astype(int)
        tp = ((preds == 1) & (y_true == 1)).sum()
        fp = ((preds == 1) & (y_true == 0)).sum()
        fn = ((preds == 0) & (y_true == 1)).sum()
        precision = tp / max(tp + fp, 1)
        recall = tp / max(tp + fn, 1)
        if recall < min_recall:
            continue
        if precision > best_precision:
            best_precision, best_t = precision, float(t)
    return best_t if best_t is not None else float(np.quantile(probs, 0.99))


def train() -> dict:
    settings = get_settings()
    artifacts = settings.artifacts_dir
    artifacts.mkdir(parents=True, exist_ok=True)

    df = load_dataset()
    df = df.sort_values("event_time").reset_index(drop=True)

    print(f"dataset: {len(df)} txns, fraud rate {df['is_fraud'].mean():.4%}")
    features, labels = build_training_features(df)
    y = np.asarray(labels)

    split = int(len(df) * 0.8)
    X_train_raw, X_test_raw = features.iloc[:split], features.iloc[split:]
    y_train, y_test = y[:split], y[split:]
    amounts_test = df["amount"].to_numpy()[split:]

    val_split = int(len(X_train_raw) * 0.9)
    X_fit, X_val = X_train_raw.iloc[:val_split], X_train_raw.iloc[val_split:]
    y_fit, y_val = y_train[:val_split], y_train[val_split:]

    X_fit_enc, cat_mappings = encode_categoricals(X_fit)
    X_val_enc, _ = encode_categoricals(X_val)
    X_test_enc, _ = encode_categoricals(X_test_raw)
    for frame in (X_val_enc, X_test_enc):
        for col in CATEGORICAL_FEATURES:
            frame[col] = pd.Categorical(
                frame[col], categories=X_fit_enc[col].cat.categories
            )

    pos = y_fit.sum()
    neg = len(y_fit) - pos
    model = lgb.LGBMClassifier(
        n_estimators=800,
        learning_rate=0.05,
        num_leaves=63,
        min_child_samples=100,
        subsample=0.9,
        subsample_freq=1,
        colsample_bytree=0.85,
        reg_lambda=1.0,
        scale_pos_weight=neg / max(pos, 1),
        random_state=42,
        verbose=-1,
    )
    model.fit(
        X_fit_enc,
        y_fit,
        eval_set=[(X_val_enc, y_val)],
        eval_metric="aucpr",
        callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)],
    )
    print(f"trained {model.best_iteration_} trees")

    probs_test = model.predict_proba(X_test_enc)[:, 1]

    review_t = pick_review_threshold(y_test, probs_test, settings.target_recall_floor)
    block_t = pick_block_threshold(y_test, probs_test, min_recall=0.5)
    if block_t <= review_t:
        block_t = min(max(block_t, review_t + 0.05), 0.995)

    cost_choice = choose_threshold_cost_based(
        y_test, probs_test, amounts_test, settings.fp_friction_cost_inr, settings.target_recall_floor
    )
    metrics_at_review = classification_metrics(y_test, probs_test, review_t)
    metrics_at_block = classification_metrics(y_test, probs_test, block_t)

    drift_baseline = {}
    numeric_cols = [c for c in FEATURE_NAMES if c not in CATEGORICAL_FEATURES]
    for col in numeric_cols:
        vals = X_test_raw[col].astype(float).to_numpy()
        edges = np.unique(np.quantile(vals, np.linspace(0, 1, 11)))
        if len(edges) >= 2:
            hist = np.histogram(vals, bins=edges)[0] / max(len(vals), 1)
            drift_baseline[col] = {"edges": edges.tolist(), "freq": hist.tolist()}

    model_version = datetime.now(UTC).strftime("v%Y%m%d-%H%M%S")
    metrics_payload = {
        "model_version": model_version,
        "trained_at": datetime.now(UTC).isoformat(),
        "dataset_rows": len(df),
        "fraud_rate": round(float(df["is_fraud"].mean()), 6),
        "split": {"train_rows": int(split), "test_rows": int(len(df) - split), "strategy": "time-based 80/20"},
        "best_iteration": int(model.best_iteration_ or model.n_estimators),
        "pr_auc": round(pr_auc(y_test, probs_test), 4),
        "roc_auc": round(roc_auc(y_test, probs_test), 4),
        "brier": round(float(brier_score_loss(y_test, probs_test)), 4),
        "review_threshold": metrics_at_review,
        "block_threshold": metrics_at_block,
        "cost_optimal_threshold": {
            "threshold": round(cost_choice["threshold"], 4),
            "recall_at_threshold": round(cost_choice["recall"] or 0, 4),
            "value_recall": round(cost_choice["value_recall"] or 0, 4),
            "fp_friction_cost_inr": settings.fp_friction_cost_inr,
        },
        "feature_importance_gain": {
            name: round(float(score), 2)
            for name, score in sorted(
                zip(FEATURE_NAMES, model.booster_.feature_importance(importance_type="gain"), strict=False),
                key=lambda kv: kv[1],
                reverse=True,
            )[:12]
        },
    }

    joblib.dump(model, artifacts / "model.joblib")
    save_json(artifacts / "features_meta.json", {"feature_names": FEATURE_NAMES, "categorical_mappings": cat_mappings})
    save_json(
        artifacts / "thresholds.json",
        {"t_review": review_t, "t_block": block_t},
    )
    save_json(artifacts / "metrics.json", metrics_payload)
    save_json(artifacts / "drift_baseline.json", drift_baseline)

    print(json.dumps({k: metrics_payload[k] for k in ("pr_auc", "roc_auc", "review_threshold", "block_threshold")}, indent=2))
    return metrics_payload


if __name__ == "__main__":
    train()
