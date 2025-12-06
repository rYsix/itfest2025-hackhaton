# app/chat/views.py

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST
import uuid

from cross.openai_use_case import OpenAIUseCase


def chat_view(request):
    """
    Страница чата.
    Если chat_id нет — создаём.
    Если история чата нет — создаём пустую.
    """
    if "chat_id" not in request.session:
        chat_id = str(uuid.uuid4())
        request.session["chat_id"] = chat_id
        request.session[f"chat_history_{chat_id}"] = []
    else:
        chat_id = request.session["chat_id"]
        key = f"chat_history_{chat_id}"
        if key not in request.session:
            request.session[key] = []

    return render(request, "chat/chat.html", {"chat_id": chat_id})


@require_POST
def api_send_message(request):
    """
    API чата.
    Получает сообщение → добавляет в историю → вызывает OpenAI с историей → сохраняет ответ.
    """
    user_text = request.POST.get("text", "").strip()

    if not user_text:
        return JsonResponse({"error": "empty message"}, status=400)

    # --------------------------------------------------------------
    # Достаём идентификатор чата и историю
    # --------------------------------------------------------------
    chat_id = request.session.get("chat_id")
    history_key = f"chat_history_{chat_id}"

    if history_key not in request.session:
        request.session[history_key] = []

    history = request.session[history_key]

    # --------------------------------------------------------------
    # Добавляем сообщение пользователя в историю
    # --------------------------------------------------------------
    history.append({"role": "user", "text": user_text})

    # --------------------------------------------------------------
    # ВЫЗОВ AI С ПОЛНОЙ ИСТОРИЕЙ
    # --------------------------------------------------------------
    ai_reply = OpenAIUseCase.tier1_support_reply(
        message=user_text,
        history=history
    )

    # --------------------------------------------------------------
    # Сохраняем ответ бота в историю
    # --------------------------------------------------------------
    history.append({"role": "assistant", "text": ai_reply})
    request.session[history_key] = history

    return JsonResponse(
        {
            "chat_id": chat_id,
            "user": user_text,
            "reply": ai_reply,
        }
    )
