"""Django settings — base + dev by default; use config.settings.prod in production."""
from .base import *  # noqa: F401,F403
from .dev import *  # noqa: F401,F403
