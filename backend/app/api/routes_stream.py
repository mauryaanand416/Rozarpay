from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.services.bus import bus

router = APIRouter(prefix="/api/v1/stream", tags=["stream"])


@router.get("/events")
def events(token: str | None = None, api_key: str | None = None):
    require_api_key_soft(token or api_key)

    def generator():
        import json
        import time

        last_id = 0
        last_beat = time.time()
        while True:
            items = bus.since(last_id)
            for item in items:
                last_id = item["id"]
                yield f"id: {item['id']}\ndata: {json.dumps(item['data'], default=str)}\n\n"
            if time.time() - last_beat > 15:
                yield ": heartbeat\n\n"
                last_beat = time.time()
            if not items:
                bus.wait(0.8)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def require_api_key_soft(token: str | None):
    from fastapi import HTTPException

    from app.config import get_settings

    if token != get_settings().api_key:
        raise HTTPException(status_code=401, detail="invalid stream token")
