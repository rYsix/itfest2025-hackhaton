import logging
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.utils.http import url_has_allowed_host_and_scheme

logger = logging.getLogger(__name__)


def login_view(request):
    ip = getattr(request, "real_ip", request.META.get("REMOTE_ADDR", "unknown"))

    # -------------------------------------------------
    # Читаем next параметр (из GET или POST)
    # -------------------------------------------------
    next_to = request.GET.get("next") or request.POST.get("next") or "/"

    # Безопасность: проверяем, что next — внутренний URL
    if not url_has_allowed_host_and_scheme(next_to, allowed_hosts={request.get_host()}):
        next_to = "/"

    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")

        if not email or not password:
            messages.error(request, "Все поля обязательны.")
            return _render(request, next_to)

        user = authenticate(request, username=email, password=password)
        if not user:
            messages.error(request, "Неверный e-mail или пароль.")
            logger.warning(f"[AUTH] invalid login attempt: {email} ({ip})")
            return _render(request, next_to)

        login(request, user)
        logger.info(f"[AUTH] successful login: {email} ({ip})")
        return redirect(next_to)

    return _render(request, next_to)


def logout_view(request):
    logout(request)
    return redirect("login")


def _render(request, next_to="/"):
    """
    Передаём next_to в шаблон, чтобы он попал в hidden input.
    """
    return render(request, "userauth/auth.html", {"next_to": next_to})
