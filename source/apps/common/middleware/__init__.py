"""
apps.common.middleware
======================

Промежуточные слои (middleware), специфичные для приложения `apps.common`.

Доступные компоненты:
* SetRealIPMiddleware — определяет реальный IP и блокирует некорректные адреса.
* ExceptionResponseAuditorMiddleware — обрабатывает исключения и ведёт аудит ответов.
* TimezoneMiddleware — активирует часовую зону из cookie.
"""

from .real_ip import SetRealIPMiddleware
from .timezone import TimezoneMiddleware

__all__ = [
    "SetRealIPMiddleware",
    "TimezoneMiddleware",
]
