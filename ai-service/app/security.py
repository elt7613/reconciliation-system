"""API-key security for the service-to-service hop.

Everything on the deployment network (dokploy-network) can reach this service,
so it must reject unauthenticated callers. The Django backend presents the
shared secret in the X-API-Key header.
"""
from fastapi import Header, HTTPException, status

from .config import settings


async def require_api_key(x_api_key: str = Header(default="")) -> None:
    if not settings.ai_service_api_key:
        # Fail closed: a misconfigured service (no key set) must not run open.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service is not configured (missing AI_SERVICE_API_KEY).",
        )
    if x_api_key != settings.ai_service_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key.")
