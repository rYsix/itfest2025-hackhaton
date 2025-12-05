from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from apps.support.models import SupportTicket, Client


# ============================================================
# СОЗДАНИЕ ЗАЯВКИ
# ============================================================

@require_http_methods(["GET", "POST"])
def support_view(request):
    """
    Создание заявки техподдержки.
    """
    context = {
        "full_name": "",
        "account_number": "",
        "description": "",
        "success": False,
        "error": None,
        "ticket_id": None,
    }

    # --------------------------------------------------------
    # GET → показать форму + предзаполнение случайным клиентом
    # --------------------------------------------------------
    if request.method == "GET":
        random_client = Client.objects.order_by("?").first()
        if random_client:
            context["full_name"] = random_client.full_name
            context["account_number"] = random_client.account_number
        return render(request, "support/create.html", context)

    # --------------------------------------------------------
    # POST
    # --------------------------------------------------------
    full_name = request.POST.get("full_name", "").strip()
    account_number = request.POST.get("account_number", "").strip()
    description = request.POST.get("description", "").strip()

    context.update({
        "full_name": full_name,
        "account_number": account_number,
        "description": description,
    })

    # ----- Валидация -----
    if not full_name or not account_number or not description:
        context["error"] = "Пожалуйста, заполните все обязательные поля."
        return render(request, "support/create.html", context)

    # -------- Поиск клиента --------
    client = Client.objects.filter(account_number=account_number).first()

    if client is None:
        context["error"] = (
            "Клиент с указанным лицевым счётом не найден. "
            "Проверьте правильность данных."
        )
        return render(request, "support/create.html", context)

    # -------- Создание тикета --------
    ticket = SupportTicket.objects.create(
        client=client,
        description=description,
        priority_score=50,
        engineer_visit_probability=0,
        status="new",
    )

    context.update({
        "success": True,
        "ticket": ticket,
    })

    return render(request, "support/create.html", context)



# ============================================================
# ПРОВЕРКА СТАТУСА ЗАЯВКИ
# ============================================================

def check_support_view(request):
    """
    Проверка статуса заявки.
    GET — форма + автоподстановка случайного ticket_code.
    POST — поиск заявки.
    """

    # --------------------------------------------------------
    # GET → показать форму + ПРЕДЗАПОЛНЕНИЕ ticket_code
    # --------------------------------------------------------
    if request.method == "GET":
        context = {}

        random_ticket = SupportTicket.objects.order_by("?").first()
        if random_ticket:
            context["ticket_id"] = random_ticket.ticket_code

        return render(request, "support/check.html", context)

    # --------------------------------------------------------
    # POST → поиск тикета
    # --------------------------------------------------------
    ticket_code = request.POST.get("ticket_id", "").strip()

    ticket = SupportTicket.objects.filter(ticket_code=ticket_code).first()

    if ticket is None:
        return render(request, "support/check.html", {
            "found": False,
            "ticket_id": ticket_code,
            "message": "Заявка не найдена",
        })

    show_engineer = (
        ticket.status in ["in_progress", "done"]
        and ticket.engineer is not None
    )

    context = {
        "found": True,
        "ticket_id": ticket.ticket_code,
        "status": ticket.get_status_display(),
        "description": ticket.description,
        "created_at": ticket.created_at,
        "closed_at": ticket.closed_at,
        "engineer": ticket.engineer.full_name if show_engineer else None,
        "show_engineer": show_engineer,
    }

    return render(request, "support/check.html", context)
