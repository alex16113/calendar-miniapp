"""
Пакет для Telegram-хендлеров (юзерский и админский флоу).
"""

from .admin import setup_admin_router  # noqa: F401
from .booking import router as booking_router  # noqa: F401
from .common import router as common_router  # noqa: F401
from .moderation import router as moderation_router  # noqa: F401
from .my_requests import router as my_requests_router  # noqa: F401

