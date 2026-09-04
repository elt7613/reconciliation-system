"""Dev overrides — verbose errors, loose CORS for the Vite dev server."""
from .base import *  # noqa: F401,F403

ALLOWED_HOSTS = ["*"]
CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS", default=["http://localhost:5173", "http://127.0.0.1:5173"])
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS
