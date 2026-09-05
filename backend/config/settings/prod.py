"""Prod overrides — strict hosts/CORS, HSTS, secure cookies, fail-closed secrets.

TLS is terminated at the deployment proxy (Dokploy/Traefik), so
SECURE_SSL_REDIRECT stays off to avoid redirect loops on setups that already
enforce HTTPS at the edge.
"""
from .base import *  # noqa: F401,F403

# SECURITY_SSL_REDIRECT left off — proxy terminates TLS (see module docstring).
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30  # 30 days
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Fail closed: production must never silently run on the insecure default key.
_INSECURE_DEFAULT_KEY = "dev-only-insecure-key-change-me"
if not SECRET_KEY or SECRET_KEY == _INSECURE_DEFAULT_KEY:  # noqa: F405
    raise RuntimeError(
        "SECRET_KEY is not set (or is the insecure default). "
        "Set a real SECRET_KEY environment variable before deploying."
    )
