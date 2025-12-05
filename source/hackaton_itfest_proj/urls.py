from django.contrib import admin
from django.urls import path, include
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

from cross import bot
from cross.openai_use_case import OpenAIUseCase


# ============================================================
# BOT CONTROL VIEWS
# ============================================================

def bot_start_view(request):
    ok = bot.start_bot()
    return JsonResponse(
        {
            "started": bool(ok),
            "message": "Bot started" if ok else "Bot already running"
        },
        json_dumps_params={"ensure_ascii": False}
    )


def bot_stop_view(request):
    ok = bot.stop_bot()
    return JsonResponse(
        {
            "stopped": bool(ok),
            "message": "Bot stopped" if ok else "Bot is not running"
        },
        json_dumps_params={"ensure_ascii": False}
    )


def bot_status_view(request):
    status = getattr(bot, "_bot_running", False)
    return JsonResponse(
        {"running": bool(status)},
        json_dumps_params={"ensure_ascii": False}
    )

# ============================================================
# OPENAI TEST VIEW (STRICT JSON)
# ============================================================

def openai_test_view(request):
    """
    Тестирует OpenAIUseCase.example_usage().
    Возвращает strict JSON (dict уже адаптирован внутри core-метода).
    """
    result = OpenAIUseCase.example_usage("Привет, сделай краткое описание текста.")

    if result is None:
        return JsonResponse(
            {"error": "OpenAI returned None"},
            status=500,
            json_dumps_params={"ensure_ascii": False}
        )

    return JsonResponse(
        result,
        safe=False,
        json_dumps_params={"ensure_ascii": False}
    )


# ============================================================
# URLS
# ============================================================

urlpatterns = [
    path("dj-admin/", admin.site.urls),

    # Redirect root → /support/
    path("", lambda request: redirect("/support/")),

    # auth endpoints
    path("auth/", include("endpoints.userauth.urls")),

    # support endpoints (обрабатывает /support/)
    path("support/", include("endpoints.support.urls")),

    path("admin/", include("endpoints.admin.urls")),

    # OPENAI TEST
    path("openai-test/", openai_test_view, name="openai_test"),

    # BOT CONTROL
    path("bot-start/", bot_start_view),
    path("bot-stop/", bot_stop_view),
    path("bot-status/", bot_status_view),
]


# ============================================================
# STATIC FILES (DEBUG)
# ============================================================

if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=getattr(settings, "MEDIA_ROOT", None),
    )
