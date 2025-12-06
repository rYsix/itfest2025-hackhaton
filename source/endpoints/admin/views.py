from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Avg
from django.db import models
from django.contrib import messages
import json

from apps.support.models import (
    SupportTicket,
    Client,
    Service,
    ClientService,
    Engineer,
)

from cross.openai_use_case import OpenAIUseCase


# ============================================================
# DASHBOARD
# ============================================================
@login_required(login_url="/auth/login/")
def admin_dashboard_view(request):
    """
    Панель администратора + аналитика для графиков.
    """

    # --------------------------------------------------------
    # 1) Список заявок
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
    # 2) Количество заявок по статусам
    # --------------------------------------------------------
    ticket_status_counts = (
        SupportTicket.objects
        .values("status")
        .annotate(total=Count("id"))
    )

    # --------------------------------------------------------
    # 3) Средний приоритет
    # --------------------------------------------------------
    avg_priority = round(
        SupportTicket.objects.aggregate(avg=Avg("priority_score"))["avg"] or 0,
        1
    )

    # --------------------------------------------------------
    # 4) Загрузка инженеров
    # --------------------------------------------------------
    engineer_load = (
        Engineer.objects
        .annotate(total_tickets=Count("supportticket"))
        .values("full_name", "total_tickets")
    )

    # --------------------------------------------------------
    # 5) Популярность услуг
    # --------------------------------------------------------
    service_usage = (
        Service.objects
        .annotate(total_users=Count("clientservice"))
        .values("title", "total_users")
    )

    # --------------------------------------------------------
    # 6) Динамика заявок
    # --------------------------------------------------------
    ticket_timeline = (
        SupportTicket.objects
        .extra(select={"day": "DATE(created_at)"})
        .values("day")
        .annotate(total=Count("id"))
        .order_by("day")
    )

    # --------------------------------------------------------
    # 7) Контекст
    # --------------------------------------------------------
    context = {
        "tickets": tickets_queryset,

        # JSON для графиков
        "ticket_status_counts_json": json.dumps(list(ticket_status_counts), ensure_ascii=False),
        "ticket_timeline_json": json.dumps(list(ticket_timeline), ensure_ascii=False),
        "engineer_load_json": json.dumps(list(engineer_load), ensure_ascii=False),
        "service_usage_json": json.dumps(list(service_usage), ensure_ascii=False),

        # Справочники
        "clients": Client.objects.all(),
        "services": Service.objects.all(),
        "client_services": ClientService.objects.select_related("client", "service"),
        "engineers": Engineer.objects.all(),
    }

    return render(request, "cadmin/dash.html", context)



# ============================================================
# AI ENGINEER PICK ASSIGNMENT
# ============================================================
@login_required(login_url="/auth/login/")
def assign_engineer_view(request, ticket_id):
    """
    Назначает инженера на основе ИИ.
    AI даёт:
        - ID инженера
        - имя
        - причину выбора
        - уверенность (0–100)
    """

    # 1) Находим заявку
    ticket = get_object_or_404(SupportTicket, id=ticket_id)

    # 2) Нельзя назначать инженера в закрытую заявку
    if ticket.status == "done":
        messages.warning(request, "Нельзя назначить инженера для закрытой заявки.")
        return redirect("admin_dashboard")

    # 3) Получаем решение ИИ
    ai_result = OpenAIUseCase.pick_engineer_for_ticket(ticket)

    if not ai_result:
        messages.error(request, "AI не смог выбрать инженера. Попробуйте позже.")
        return redirect("admin_dashboard")

    engineer_id = ai_result.get("engineer_id")
    reason = ai_result.get("reason", "Причина не указана AI.")
    confidence = ai_result.get("confidence", 0)

    # 4) Проверяем инженера в БД
    engineer = Engineer.objects.filter(id=engineer_id).first()
    if not engineer:
        messages.error(request, "AI выбрал инженера, которого нет в базе.")
        return redirect("admin_dashboard")

    # 5) Применяем назначение
    ticket.engineer = engineer
    ticket.status = "in_progress"
    ticket.save(update_fields=["engineer", "status"])

    # 6) Красивый вывод причины
    messages.success(
        request,
        f"AI назначил инженера «{engineer.full_name}» "
        f"для заявки #{ticket.ticket_code}.<br>"
        f"<b>Причина:</b> {reason}<br>"
        f"<b>Уверенность:</b> {confidence}%"
    )

    return redirect("admin_dashboard")
