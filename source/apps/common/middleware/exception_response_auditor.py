# apps/common/middleware/exception_response_auditor.py
# -*- coding: utf-8 -*-
"""
Аудитор исключений и ответов (Exception/Response Auditor)

- Исключения → логируются с уровнем error и отображаются через шаблон (400/403/404/500).
  Если шаблон отсутствует — возвращается простой текст.
- Ответы → сводный лог (только если ≥100 событий или прошло ≥3 часов).
- Автоответ (Auto Answer) → при превышении лимита по IP запрос блокируется
  с заданным кодом (например, 444). Событие фиксируется в сводке.
- Для логов используется request.obscured_ip.
- Для ключей кеша и лимитов используется request.real_ip.
"""

import logging
import time
from datetime import datetime
from http.client import responses as HTTP_STATUS_TEXT

from django.core.cache import cache
from django.core.exceptions import (
    BadRequest, DisallowedHost, DisallowedRedirect, FieldDoesNotExist,
    PermissionDenied, RequestDataTooBig, SuspiciousOperation, ValidationError,
)
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.template import TemplateDoesNotExist

SAFE_STATUS_CODES = {200, 301, 302}

TEMPLATE_BY_CODE = {400: "400.html", 403: "403.html", 404: "404.html", 500: "500.html"}

SUMMARY_CACHE_KEY = "audit-summary"
SUMMARY_LIMIT = 200
SUMMARY_TTL = 60 * 60 * 12  # 12 часов

AUTO_ANSWER_RULES = {
    "response_403": {
        "limit": 4,
        "timeout": 60 * 60 * 3,  # 3 часа
        "ip_all": False,
        "answer_code": 444,
    },
}


class ExceptionResponseAuditorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = logging.getLogger(__name__)

    def __call__(self, request: HttpRequest) -> HttpResponse:
        auto_answer = self._check_auto_answer(request)
        if auto_answer:
            return auto_answer

        try:
            response = self.get_response(request)
        except Exception as exc:
            request._exception_logged = True
            return self._handle_exception(request, exc)

        if not getattr(request, "_exception_logged", False):
            self._audit_response(request, response)

        return response

    def process_exception(self, request: HttpRequest, exception: Exception):
        request._exception_logged = True
        return self._handle_exception(request, exception)

    # ---- Автоответ ----
    def _check_auto_answer(self, request: HttpRequest):
        ip_real = getattr(request, "real_ip", "unknown")

        for slug, rule in AUTO_ANSWER_RULES.items():
            ip_key = "*" if rule["ip_all"] else ip_real
            key = f"auto-answer:{slug}:{ip_key}"
            count = cache.get(key) or 0

            if count >= rule["limit"]:
                status_code = int(rule["answer_code"])
                ctx = self._ctx(request)
                ctx.update({
                    "slug": f"auto_answer_{slug}",
                    "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                    "auto_answer_triggered": True,
                    "status": status_code,
                })

                data = cache.get(SUMMARY_CACHE_KEY) or {"events": [], "start_ts": time.time()}
                data["events"].append(ctx)

                time_passed = (time.time() - data["start_ts"]) > SUMMARY_TTL
                enough_events = len(data["events"]) >= SUMMARY_LIMIT
                if time_passed or enough_events:
                    self._flush_summary(data)
                    data = {"events": [], "start_ts": time.time()}

                cache.set(SUMMARY_CACHE_KEY, data, timeout=SUMMARY_TTL)
                return HttpResponse(status=status_code)

        return None

    # ---- Обработка исключений ----
    def _handle_exception(self, request: HttpRequest, exc: Exception) -> HttpResponse:
        if isinstance(
            exc,
            (ValidationError, SuspiciousOperation, RequestDataTooBig,
             FieldDoesNotExist, DisallowedHost, DisallowedRedirect, BadRequest),
        ):
            code, reason = 400, "Bad Request"
        elif isinstance(exc, PermissionDenied):
            code, reason = 403, "Forbidden"
        elif isinstance(exc, Http404):
            code, reason = 404, "Not Found"
        else:
            code, reason = 500, "Internal Server Error"

        template = TEMPLATE_BY_CODE.get(code, "500.html")

        ip_log = getattr(request, "obscured_ip", "unknown")
        exc_text = str(exc).strip()
        details = f": '{exc_text}'" if exc_text else ""

        msg = (
            f"Exception {code} {type(exc).__name__}{details}\n"
            f"Path={getattr(request, 'path', '<no-path>')}, "
            f"Method={getattr(request, 'method', '<no-method>')}, "
            f"IP={ip_log}\n"
            f"→ Categorized as {code} {reason}; template={template}"
        )
        ctx = self._ctx(request, status_code=code)
        self.logger.error(msg, exc_info=exc, extra={"extra": {"request": ctx}})

        try:
            return render(request, template, status=code)
        except TemplateDoesNotExist:
            return HttpResponse(f"{code} {reason}", status=code)

    # ---- Аудит ответов ----
    def _audit_response(self, request: HttpRequest, response: HttpResponse) -> None:
        status = response.status_code
        if status in SAFE_STATUS_CODES:
            return

        slug = f"response_{status}"
        ctx = self._ctx(request, response=response)
        ctx.update({
            "slug": slug,
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        })

        rule = AUTO_ANSWER_RULES.get(slug)
        if rule:
            ip_real = getattr(request, "real_ip", "unknown")
            ip_key = "*" if rule["ip_all"] else ip_real
            key = f"auto-answer:{slug}:{ip_key}"
            count = (cache.get(key) or 0) + 1
            cache.set(key, count, timeout=rule["timeout"])

        data = cache.get(SUMMARY_CACHE_KEY) or {"events": [], "start_ts": time.time()}
        data["events"].append(ctx)

        time_passed = (time.time() - data["start_ts"]) > SUMMARY_TTL
        enough_events = len(data["events"]) >= SUMMARY_LIMIT
        if time_passed or enough_events:
            self._flush_summary(data)
            data = {"events": [], "start_ts": time.time()}

        cache.set(SUMMARY_CACHE_KEY, data, timeout=SUMMARY_TTL)

    # ---- Формирование сводки ----
    def _flush_summary(self, data: dict) -> None:
        events = data.get("events", [])
        if not events:
            return

        total = len(events)
        first_ts = events[0]["timestamp"]
        last_ts = events[-1]["timestamp"]

        grouped = {}
        for e in events:
            grouped.setdefault(e["slug"], []).append(e)

        lines = [
            f"Сводка: {total} неуспешных ответов",
            f"Период: {first_ts} → {last_ts}",
        ]

        for slug, group in grouped.items():
            lines.append(f" - {slug}: {len(group)}")

            by_ip = {}
            for ex in group:
                ip = ex["ip"]
                by_ip.setdefault(ip, []).append(ex)

            for ip, items in by_ip.items():
                sample = items[0]
                count = len(items)
                status = sample.get("status", 0)

                if slug.startswith("auto_answer_"):
                    lines.append(f"    ip={ip} → {count} срабатываний, АВТООТВЕТ {status}")
                else:
                    lines.append(
                        f"    ip={ip} → {count} раз, статус={status} "
                        f"{HTTP_STATUS_TEXT.get(status, 'Unknown')}"
                    )

        dedup = {}
        for e in events:
            key = (e["ip"], e["slug"], e["status"], e["method"],
                   e["user_agent"], e["referer"])
            if key not in dedup:
                dedup[key] = {
                    "ip": e["ip"],
                    "slug": e["slug"],
                    "status": e["status"],
                    "method": e["method"],
                    "user_agent": e["user_agent"],
                    "referer": e["referer"],
                    "hits": 0,
                    "first_seen": e["timestamp"],
                    "last_seen": e["timestamp"],
                    "paths": set(),
                }
            dedup[key]["hits"] += 1
            dedup[key]["last_seen"] = e["timestamp"]
            dedup[key]["paths"].add(e["path"])

        dedup_list = []
        for d in dedup.values():
            d["paths"] = list(d["paths"])
            dedup_list.append(d)

        msg = "\n".join(lines)
        self.logger.warning(msg, extra={"extra": {"requests": dedup_list}})

    # ---- Вспомогательные ----
    def _ctx(self, request: HttpRequest, *, status_code=None, response=None):
        """Извлекает контекст запроса для логирования (без данных пользователя)."""
        meta = getattr(request, "META", {}) or {}

        try:
            get_data = dict(request.GET)
        except Exception:
            get_data = {"_unavailable": True}
        try:
            post_data = dict(request.POST) if request.method in ("POST", "PUT", "PATCH") else {}
        except Exception:
            post_data = {"_unavailable": True}

        return {
            "path": getattr(request, "path", "<no-path>"),
            "method": getattr(request, "method", "<no-method>"),
            "ip": getattr(request, "obscured_ip", "unknown"),
            "user_agent": meta.get("HTTP_USER_AGENT", "unknown"),
            "accept_language": meta.get("HTTP_ACCEPT_LANGUAGE", "unknown"),
            "referer": meta.get("HTTP_REFERER", "unknown"),
            "protocol": meta.get("SERVER_PROTOCOL", "unknown"),
            "GET": get_data,
            "POST": post_data,
            "status": status_code or getattr(response, "status_code", None),
        }
