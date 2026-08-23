import json
from pathlib import Path

import numpy as np


def classification_metrics(y_true, probs, threshold: float) -> dict:
    y_true = np.asarray(y_true).astype(int)
    preds = (probs >= threshold).astype(int)

    tp = int(((preds == 1) & (y_true == 1)).sum())
    fp = int(((preds == 1) & (y_true == 0)).sum())
    fn = int(((preds == 0) & (y_true == 1)).sum())
    tn = int(((preds == 0) & (y_true == 0)).sum())

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    beta2 = 5
    f2_denom = (beta2 * precision + recall)
    f2 = (1 + beta2**2) * precision * recall / (beta2**2 * precision + recall) if f2_denom else 0.0

    return {
        "threshold": round(float(threshold), 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "f2": round(f2, 4),
        "confusion_matrix": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
    }


def pr_auc(y_true, probs) -> float:
    from sklearn.metrics import average_precision_score

    return float(average_precision_score(y_true, probs))


def roc_auc(y_true, probs) -> float:
    from sklearn.metrics import roc_auc_score

    return float(roc_auc_score(y_true, probs))


def choose_threshold_cost_based(
    y_true, probs, amounts, fp_cost: float = 150.0, recall_floor: float = 0.80
) -> dict:
    y_true = np.asarray(y_true).astype(int)
    amounts = np.asarray(amounts, dtype=float)

    best = None
    grid = np.unique(np.quantile(probs, np.linspace(0.01, 0.99, 197)))
    for t in grid:
        preds = (probs >= t).astype(int)
        tp = ((preds == 1) & (y_true == 1)).sum()
        fn = ((preds == 0) & (y_true == 1)).sum()
        fp = ((preds == 1) & (y_true == 0)).sum()
        missed_value = float(amounts[(preds == 0) & (y_true == 1)].sum())
        total_fraud_value = float(amounts[y_true == 1].sum()) or 1.0
        value_recall = 1 - missed_value / total_fraud_value
        cost = missed_value + fp * fp_cost
        recall = tp / max(tp + fn, 1)

        candidate = {
            "threshold": float(t),
            "cost": cost,
            "recall": float(recall),
            "value_recall": float(value_recall),
        }
        if recall < recall_floor:
            continue
        if best is None or cost < best["cost"]:
            best = candidate

    if best is None:
        best = {"threshold": 0.5, "cost": None, "recall": None, "value_recall": None}
    return best


def psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    expected = np.asarray(expected, dtype=float)
    actual = np.asarray(actual, dtype=float)
    edges = np.unique(np.quantile(expected, np.linspace(0, 1, bins + 1)))
    if len(edges) < 2:
        return 0.0
    edges[0], edges[-1] = -np.inf, np.inf
    e_hist = np.histogram(expected, bins=edges)[0] / max(len(expected), 1)
    a_hist = np.histogram(actual, bins=edges)[0] / max(len(actual), 1)
    eps = 1e-6
    e_hist = np.clip(e_hist, eps, None)
    a_hist = np.clip(a_hist, eps, None)
    return float(np.sum((a_hist - e_hist) * np.log(a_hist / e_hist)))


def save_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, default=str))
