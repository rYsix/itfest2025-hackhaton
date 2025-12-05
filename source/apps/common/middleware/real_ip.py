# apps/common/middleware/real_ip.py
# -*- coding: utf-8 -*-
"""
SetRealIPMiddleware

- Определяет реальный IP клиента через ipware.
- Добавляет request.real_ip и request.obscured_ip.
- Если IP некорректен (loopback, multicast, reserved и т.д.) — возвращает 403.
- При включённом DEBUG некорректные IP пропускаются.
"""

import ipaddress
from django.conf import settings
from django.http import HttpResponseForbidden
from ipware import get_client_ip


class SetRealIPMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ip, _ = get_client_ip(request)
        request.real_ip = ip or None
        request.obscured_ip = self._mask_ip(ip) if ip else "unknown"

        if not self._is_valid_ip(ip) and not getattr(settings, "DEBUG", False):
            return HttpResponseForbidden("Ваш IP некорректен. Запрос отклонён.")

        return self.get_response(request)

    # ------------------------------------------------------------------ #
    # Вспомогательные методы                                             #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _is_valid_ip(ip: str | None) -> bool:
        """Проверяет корректность IP (исключая служебные, loopback и т.п.)."""
        try:
            if not ip:
                return False
            ip_obj = ipaddress.ip_address(ip)
            return not (
                ip_obj.is_unspecified
                or ip_obj.is_loopback
                or ip_obj.is_multicast
                or ip_obj.is_link_local
                or ip_obj.is_reserved
            )
        except ValueError:
            return False

    @staticmethod
    def _mask_ip(ip: str | None) -> str:
        """Возвращает замаскированный IP для логов."""
        if not ip:
            return "unknown"
        try:
            ip_obj = ipaddress.ip_address(ip)
            if ip_obj.version == 4:
                parts = ip.split(".")
                return f"{parts[0]}.*.*.{parts[3]}"
            if ip_obj.version == 6:
                parts = ip.split(":")
                return f"{parts[0]}:*:*:*::{parts[-1]}"
        except ValueError:
            return "unknown"
