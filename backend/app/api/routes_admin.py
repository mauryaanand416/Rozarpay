import threading

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_api_key
from app.config import get_settings
from app.db.base import get_db
from app.llm.client import llm_provider_name
from app.llm.digest import generate_digest
from app.ml.predict import get_registry
from app.simulator.generator import simulator

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

_retrain_lock = threading.Lock()
_jobs: dict[str, dict] = {}


@router.post("/simulator/start", dependencies=[Depends(require_api_key)])
def start_simulator():
    started = simulator.start()
    return {"running": simulator.running, "started_now": started}


@router.post("/simulator/stop", dependencies=[Depends(require_api_key)])
def stop_simulator():
    stopped = simulator.stop()
    return {"running": simulator.running, "stopped_now": stopped}


@router.get("/simulator/status", dependencies=[Depends(require_api_key)])
def simulator_status():
    return {"running": simulator.running, "processed": simulator.processed}


@router.post("/digest/generate", dependencies=[Depends(require_api_key)])
def digest(hours: int = 24, db: Session = Depends(get_db)):
    hours = min(max(hours, 1), 168)
    return generate_digest(db, hours=hours)


@router.post("/model/retrain", dependencies=[Depends(require_api_key)])
def retrain():
    if not _retrain_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="retrain already in progress")
    job_id = f"retrain-{len(_jobs) + 1}"
    _jobs[job_id] = {"status": "running", "started_at": None, "error": None, "metrics": None}

    def _run():
        try:
            from app.ml.predict import get_registry as reg
            from app.ml.train import train

            metrics = train()
            reg().reload()
            _jobs[job_id].update(status="done", metrics=metrics["review_threshold"])
        except Exception as exc:
            _jobs[job_id].update(status="failed", error=str(exc))
        finally:
            _retrain_lock.release()

    threading.Thread(target=_run, daemon=True).start()
    return {"job": job_id, "status": "running"}


@router.get("/model/status", dependencies=[Depends(require_api_key)])
def model_status():
    registry = get_registry()
    settings = get_settings()
    latest_job = _jobs and max(_jobs.keys())
    return {
        "model_available": registry.available,
        "model_version": registry.version,
        "load_error": registry.load_error,
        "safe_mode": not registry.available,
        "llm_provider": llm_provider_name(),
        "hard_gate_amount_inr": settings.hard_gate_amount,
        "last_retrain_job": {k: _jobs[k] for k in [latest_job] if latest_job} or None,
    }
