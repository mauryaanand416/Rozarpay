from fastapi import HTTPException, Request

from app.config import get_settings


def require_api_key(request: Request):
    settings = get_settings()
    key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
    if key != settings.api_key:
        raise HTTPException(status_code=401, detail="invalid or missing API key")
