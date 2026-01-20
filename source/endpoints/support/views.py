import logging

from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from apps.support.models import SupportTicket, Client, Engineer
from cross.openai_use_case import OpenAIUseCase
from cross.utils import calculate_final_priority


logger = logging.getLogger(__name__)


# ============================================================
#                     СОЗДАНИЕ ЗАЯВКИ
# ============================================================

@require_http_methods(["GET", "POST"])
def support_view(request):
    """
    Создание заявки техподдержки.
    GET  → пустая форма
    POST → принимает данные, вызывает AI, создаёт тикет
    """

    context = {
        "full_name": "",
        "account_number": "",
        "description": "",
        "success": False,
        "error": None,
        "ticket": None,
    }

    # --------------------------------------------------------
    # GET → просто форма, БЕЗ предзаполнения
    # --------------------------------------------------------
    if request.method == "GET":
        return render(request, "support/create.html", context)

    # --------------------------------------------------------
    # POST → получение данных
    # --------------------------------------------------------
    full_name = request.POST.get("full_name", "").strip()
    account_number = request.POST.get("account_number", "").strip()
    description = request.POST.get("description", "").strip()

    context.update({
        "full_name": full_name,
        "account_number": account_number,
        "description": description,
    })

    # --------------------------------------------------------
    # ВАЛИДАЦИЯ
    # --------------------------------------------------------
    if not full_name or not account_number or not description:
        context["error"] = "Пожалуйста, заполните все обязательные поля."
        return render(request, "support/create.html", context)

    if not OpenAIUseCase.classify_telecom_issue(description):
        context["error"] = "Описание проблемы не относится к услугам Казахтелекома."
        return render(request, "support/create.html", context)

    # --------------------------------------------------------
    # ПОИСК КЛИЕНТА
    # --------------------------------------------------------
    client = Client.objects.filter(
        account_number=account_number,
        full_name=full_name
    ).first()

    if client is None:
        context["error"] = (
            "Клиент с указанными данными не найден. "
            "Проверьте ФИО и лицевой счёт."
        )
        return render(request, "support/create.html", context)

    # --------------------------------------------------------
    # AI → единый анализ заявки
    # --------------------------------------------------------
    ai = OpenAIUseCase.generate_full_ticket_ai(
        description=description,
        age=client.age
    )

    if ai is None:
        context["error"] = "AI-сервис временно недоступен. Попробуйте позже."
        return render(request, "support/create.html", context)

    client_advice      = ai.get("client_advice", "")
    engineer_advice    = ai.get("engineer_advice", "")
    engineer_prob      = ai.get("engineer_probability", 0)
    engineer_prob_expl = ai.get("engineer_probability_explanation", "")
    initial_priority   = ai.get("initial_priority", 50)

    final_priority = calculate_final_priority(
        int(initial_priority),
        client
    )

    # --------------------------------------------------------
    # СОЗДАНИЕ ТИКЕТА
    # --------------------------------------------------------
    ticket = SupportTicket.objects.create(
        client=client,
        description=description,
        priority_score=final_priority,
        engineer_visit_probability=engineer_prob,
        why_engineer_needed=engineer_prob_expl,
        proposed_solution_engineer=engineer_advice,
        proposed_solution_client=client_advice,
        status="new",
    )

    # --------------------------------------------------------
    # AI → подбор инженера
    # --------------------------------------------------------
    engineer_pick = OpenAIUseCase.pick_engineer_for_ticket(ticket)

    if engineer_pick:
        engineer_id = engineer_pick.get("engineer_id")

        engineer = Engineer.objects.filter(
            id=engineer_id,
            is_active=True
        ).first()

        if engineer:
            ticket.engineer = engineer
            ticket.save(update_fields=["engineer"])

            logger.info(
                "Engineer assigned by AI",
                extra={
                    "ticket_id": ticket.id,
                    "engineer_id": engineer.id,
                    "engineer_name": engineer.full_name,
                    "confidence": engineer_pick.get("confidence"),
                    "reason": engineer_pick.get("reason"),
                },
            )

    context.update({
        "success": True,
        "ticket": ticket,
    })

    return render(request, "support/create.html", context)


# ============================================================
#                ПРОВЕРКА СТАТУСА ЗАЯВКИ
# ============================================================

@require_http_methods(["GET", "POST"])
def check_support_view(request):
    """
    Проверка статуса заявки.
    GET  → пустая форма
    POST → поиск заявки по коду
    """

    # --------------------------------------------------------
    # GET → форма без автозаполнения
    # --------------------------------------------------------
    if request.method == "GET":
        return render(request, "support/check.html", {})

    # --------------------------------------------------------
    # POST → поиск тикета
    # --------------------------------------------------------
    ticket_code = request.POST.get("ticket_id", "").strip()

    ticket = SupportTicket.objects.filter(
        ticket_code=ticket_code
    ).first()

    if ticket is None:
        return render(
            request,
            "support/check.html",
            {
                "found": False,
                "ticket_id": ticket_code,
                "message": "Заявка не найдена",
            },
        )

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
