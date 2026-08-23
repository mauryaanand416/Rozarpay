import json

import pandas as pd
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_api_key
from app.config import get_settings
from app.db.base import get_db
from app.db.models import Decision
from app.ml.evaluate import psi

router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"])


@router.get("/model", dependencies=[Depends(require_api_key)])
def model_metrics():
    path = get_settings().artifacts_dir / "metrics.json"
    if not path.exists():
        return {"status": "not_trained"}
    return json.loads(path.read_text())


@router.get("/live", dependencies=[Depends(require_api_key)])
def live_metrics(db: Session = Depends(get_db)):
    from app.llm.digest import collect_stats

    return collect_stats(db, hours=24)


@router.get("/drift", dependencies=[Depends(require_api_key)])
def drift(db: Session = Depends(get_db)):
    settings = get_settings()
    baseline_path = settings.artifacts_dir / "drift_baseline.json"
    if not baseline_path.exists():
        return {"status": "no_baseline"}

    rows = (
        db.query(Decision.features)
        .order_by(Decision.id.desc())
        .limit(500)
        .all()
    )
    feats = [r[0] for r in rows if r[0]]
    if len(feats) < 50:
        return {"status": "insufficient_data", "samples": len(feats)}

    frame = pd.DataFrame(feats)
    baseline = json.loads(baseline_path.read_text())
    results = {}
    for col, spec in baseline.items():
        if col not in frame.columns:
            continue
        edges = spec["edges"]
        expected = spec["freq"]
        actual_hist = pd.cut(pd.to_numeric(frame[col], errors="coerce"), bins=edges).value_counts()
        counts = actual_hist.reindex(sorted(actual_hist.index), fill_value=0)
        total = int(counts.sum()) or 1
        actual = (counts / total).to_numpy()
        score = psi(expected, actual)
        results[col] = round(score, 4)

    ranked = dict(sorted(results.items(), key=lambda kv: kv[1], reverse=True)[:8])
    alerts = [k for k, v in ranked.items() if v > 0.25]
    return {
        "status": "alert" if alerts else "healthy",
        "psi_by_feature": ranked,
        "alerts": alerts,
        "note": "PSI > 0.25 suggests distribution drift; consider retraining",
        "samples": len(feats),
    }
