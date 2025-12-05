# apps/support/views.py

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db import models   # ← ВАЖНО: нужен для Case / When / IntegerField

from apps.support.models import (
    SupportTicket,
    Client,
    Service,
    ClientService,
    Engineer,
)


@login_required(login_url="/auth/login/")
def admin_dashboard_view(request):
    """
    Панель администратора: список заявок + данные для аналитики.
    """

    # --------------------------------------------------------
    # СОРТИРОВКА
    # new / in_progress → в начале
    # done → в конце
    # priority_score → по убыванию
    # created_at → по возрастанию
    # --------------------------------------------------------
    tickets_queryset = (
        SupportTicket.objects
        .select_related("client", "engineer")
        .order_by(
            models.Case(
                models.When(status="done", then=2),
                default=1,
                output_field=models.IntegerField(),
            ),
            "-priority_score",
            "created_at",
        )
    )

    # --------------------------------------------------------
    # КОНТЕКСТ
    # --------------------------------------------------------
    context = {
        "clients": Client.objects.all(),
        "services": Service.objects.all(),
        "client_services": ClientService.objects.select_related("client", "service"),
        "engineers": Engineer.objects.all(),
        "tickets": tickets_queryset,
    }

    return render(request, "cadmin/dash.html", context)
