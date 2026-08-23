import logging
import threading

import httpx

logger = logging.getLogger("sentipay.webhooks")


def notify_block(payload: dict) -> None:
    from app.config import get_settings

    url = get_settings().webhook_url
    if not url:
        return

    def _post():
        try:
            httpx.post(url, json={"event": "risk.decision", "data": payload}, timeout=5.0)
        except Exception as exc:
            logger.warning("webhook delivery failed (ignored): %s", exc)

    threading.Thread(target=_post, daemon=True).start()
