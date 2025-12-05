import logging
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect

logger = logging.getLogger(__name__)


def login_view(request):
    ip = getattr(request, "real_ip", request.META.get("REMOTE_ADDR", "unknown"))

    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")

        if not email or not password:
            messages.error(request, "Все поля обязательны.")
            return _render(request)

        user = authenticate(request, username=email, password=password)
        if not user:
            messages.error(request, "Неверный e-mail или пароль.")
            logger.warning(f"[AUTH] invalid login attempt: {email} ({ip})")
            return _render(request)

        login(request, user)
        logger.info(f"[AUTH] successful login: {email} ({ip})")
        return redirect("/")

    return _render(request)


def logout_view(request):
    logout(request)
    return redirect("login")


def _render(request):
    return render(request, "userauth/auth.html")
