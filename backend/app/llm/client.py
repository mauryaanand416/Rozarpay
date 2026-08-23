import logging
import threading
import time

logger = logging.getLogger("sentipay.llm")


class CircuitBreaker:
    def __init__(self, max_failures: int, cooldown_seconds: float):
        self.max_failures = max_failures
        self.cooldown_seconds = cooldown_seconds
        self._failures = 0
        self._opened_at: float | None = None
        self._lock = threading.Lock()

    @property
    def is_open(self) -> bool:
        with self._lock:
            if self._opened_at is None:
                return False
            if time.monotonic() - self._opened_at >= self.cooldown_seconds:
                self._opened_at = None
                self._failures = 0
                return False
            return True

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._opened_at = None

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= self.max_failures:
                self._opened_at = time.monotonic()
                logger.warning("llm circuit breaker OPEN for %.0fs", self.cooldown_seconds)


_state_lock = threading.Lock()
_client = None
_provider: str | None = None


def _get_client():
    global _client, _provider
    with _state_lock:
        if _client is not None:
            return _client, _provider
        from app.config import get_settings

        settings = get_settings()
        try:
            from openai import AzureOpenAI, OpenAI
        except ImportError:
            return None, None

        if settings.has_azure_openai:
            _client = AzureOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                api_key=settings.azure_openai_api_key,
                api_version=settings.azure_openai_api_version,
                timeout=settings.llm_timeout_seconds,
                max_retries=0,
            )
            _provider = "azure-openai"
        elif settings.has_openai:
            _client = OpenAI(api_key=settings.openai_api_key, timeout=settings.llm_timeout_seconds, max_retries=0)
            _provider = "openai"
        else:
            _client = False
            _provider = None
        return _client if _client else None, _provider


def llm_provider_name() -> str:
    _, provider = _get_client()
    return provider or "none"


def chat_completion(system: str, user: str) -> str | None:
    from app.config import get_settings

    settings = get_settings()

    client, provider = _get_client()
    if client is None:
        return None
    if _breaker.is_open:
        return None

    model = (
        settings.azure_openai_deployment if provider == "azure-openai" else settings.openai_model
    )
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user[:6000]},
            ],
            temperature=0.2,
            max_tokens=300,
        )
        text = (response.choices[0].message.content or "").strip() or None
    except Exception as exc:
        logger.info("llm call failed: %s", type(exc).__name__)
        _breaker.record_failure()
        return None
    if text:
        _breaker.record_success()
    return text


_breaker = CircuitBreaker(
    max_failures=3,
    cooldown_seconds=60.0,
)
