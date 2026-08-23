import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.rate_limit import RateLimitMiddleware
from app.config import get_settings
from app.db.base import init_db

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    from app.ml.predict import get_registry

    registry = get_registry()
    if not registry.available:
        logger.warning("model artifacts missing - running in SAFE MODE (all txns -> review)")
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        description=(
            "AI Risk Manager for the Razorpay AI Buildathon Track 02: real-time fraud "
            "detection with measured precision/recall, explainable decisions, gated actions "
            "and a tamper-evident audit trail."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(RateLimitMiddleware, per_minute=settings.rate_limit_per_minute)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from app.api.routes_admin import router as admin_router
    from app.api.routes_audit import router as audit_router
    from app.api.routes_metrics import router as metrics_router
    from app.api.routes_queue import router as queue_router
    from app.api.routes_stream import router as stream_router
    from app.api.routes_transactions import router as txn_router

    app.include_router(txn_router)
    app.include_router(queue_router)
    app.include_router(audit_router)
    app.include_router(metrics_router)
    app.include_router(admin_router)
    app.include_router(stream_router)

    @app.get("/healthz", tags=["ops"])
    def healthz():
        from app.llm.client import llm_provider_name
        from app.ml.predict import get_registry

        registry = get_registry()
        return {
            "status": "ok",
            "safe_mode": not registry.available,
            "model": {"available": registry.available, "version": registry.version},
            "llm_provider": llm_provider_name(),
            "simulator_running": _simulator_running(),
        }

    return app


def _simulator_running() -> bool:
    try:
        from app.simulator.generator import simulator

        return simulator.running
    except Exception:
        return False


app = create_app()

