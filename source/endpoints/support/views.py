from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from apps.support.models import SupportTicket, Client
from cross.openai_use_case import OpenAIUseCase
from cross.utils import calculate_final_priority


# ============================================================
#                     СОЗДАНИЕ ЗАЯВКИ
# ============================================================

@require_http_methods(["GET", "POST"])
def support_view(request):
    """
    Создание заявки техподдержки.
    GET  → показывает форму с подстановкой случайного клиента.
    POST → принимает входные данные, вызывает AI, создаёт тикет.
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
    # GET → отображение формы
    # --------------------------------------------------------
    if request.method == "GET":
        random_client = Client.objects.order_by("?").first()

        if random_client:
            context["full_name"] = random_client.full_name
            context["account_number"] = random_client.account_number

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
    client = Client.objects.filter(account_number=account_number).first()

    if client is None:
        context["error"] = (
            "Клиент с указанным лицевым счётом не найден. "
            "Проверьте правильность данных."
        )
        return render(request, "support/create.html", context)

    # --------------------------------------------------------
    # HOOK #1 — место для логирования, антифрода, доп. проверки
    # --------------------------------------------------------
    # example: RiskAnalyzer.log_request(client, description)
    # --------------------------------------------------------

    # --------------------------------------------------------
    # AI → единый запрос
    # --------------------------------------------------------
    ai = OpenAIUseCase.generate_full_ticket_ai(description, client.age)

    if ai is None:
        context["error"] = "AI-сервис временно недоступен. Попробуйте позже."
        return render(request, "support/create.html", context)

    # Распаковка результата
    client_advice              = ai.get("client_advice", "")
    engineer_advice            = ai.get("engineer_advice", "")
    engineer_prob              = ai.get("engineer_probability", 0)
    engineer_prob_expl         = ai.get("engineer_probability_explanation", "")
    initial_priority           = ai.get("initial_priority", 50)

    final_priority = calculate_final_priority(int(initial_priority), client)

    # --------------------------------------------------------
    # HOOK #2 — место для автоприсвоения инженера или правил SLA
    # --------------------------------------------------------
    # example:
    # assigned_engineer = EngineerAssignmentService.assign(client, final_priority)
    # --------------------------------------------------------

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
    GET  → форма + подстановка случайного ticket_code.
    POST → поиск заявки.
    """

    # --------------------------------------------------------
    # GET → форма с авто-заполнением случайной заявки
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
