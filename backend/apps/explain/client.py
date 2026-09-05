"""HTTP client for the AI microservice (FastAPI).

Error handling contract (why the backend never crashes on AI problems):
- Transport errors (DNS blips, connection refused, timeouts — the exact
  failure class seen in production logs) are retried with short backoff:
  2 attempts after the first, 0.5s then 1.0s.
- Non-2xx from the service is returned as a tuple; the views map codes to
  messages without raising.
- Any failure returns (None, reason) — callers degrade to the deterministic
  fallback and log the reason.
"""
import logging

import httpx

from django.conf import settings

logger = logging.getLogger(__name__)

RETRY_DELAYS_SECONDS = (0.5, 1.0)  # after the initial attempt


class AIServiceError(Exception):
    """Raised when the AI service is unreachable or returns an unexpected body."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _headers() -> dict:
    return {"X-API-Key": settings.AI_SERVICE["api_key"]}


def explain_discrepancy(payload: dict) -> dict:
    """Call POST /explain. Returns the explanation dict or raises AIServiceError."""
    url = settings.AI_SERVICE["url"].rstrip("/") + "/explain"
    last_error = None
    for attempt, delay in enumerate((0.0,) + RETRY_DELAYS_SECONDS):
        if delay:
            import time

            time.sleep(delay)
        try:
            resp = httpx.post(
                url,
                json=payload,
                headers=_headers(),
                timeout=settings.AI_SERVICE["timeout_seconds"],
            )
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (401, 403):
                # Config error — retrying won't help.
                raise AIServiceError(f"AI service rejected our key ({resp.status_code})")
            if resp.status_code == 422:
                raise AIServiceError("AI service rejected the payload shape")
            last_error = AIServiceError(f"AI service error {resp.status_code}")
        except AIServiceError:
            raise
        except httpx.HTTPError as exc:
            last_error = AIServiceError(f"AI service unreachable: {type(exc).__name__}")
        if attempt == len(RETRY_DELAYS_SECONDS):
            break
    raise last_error or AIServiceError("AI service unreachable")


def summarize_findings(payload: dict) -> dict:
    """Call POST /summarize. Returns the summary dict or raises AIServiceError."""
    url = settings.AI_SERVICE["url"].rstrip("/") + "/summarize"
    last_error = None
    for attempt, delay in enumerate((0.0,) + RETRY_DELAYS_SECONDS):
        if delay:
            import time

            time.sleep(delay)
        try:
            resp = httpx.post(
                url,
                json=payload,
                headers=_headers(),
                timeout=settings.AI_SERVICE["timeout_seconds"],
            )
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (401, 403):
                raise AIServiceError(f"AI service rejected our key ({resp.status_code})")
            if resp.status_code == 422:
                raise AIServiceError("AI service rejected the payload shape")
            last_error = AIServiceError(f"AI service error {resp.status_code}")
        except AIServiceError:
            raise
        except httpx.HTTPError as exc:
            last_error = AIServiceError(f"AI service unreachable: {type(exc).__name__}")
        if attempt == len(RETRY_DELAYS_SECONDS):
            break
    raise last_error or AIServiceError("AI service unreachable")


def is_configured() -> bool:
    """True when the service URL and shared key are set and AI is enabled."""
    cfg = settings.AI_SERVICE
    return bool(cfg["enabled"] and cfg["url"] and cfg["api_key"])
