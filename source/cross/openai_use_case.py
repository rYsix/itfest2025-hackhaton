"""
CORE OpenAI JSON Helper + Ticket AI Resolver.

Добавлено:
- Автоматический выбор языка через get_language()
- Инструкция в system_prompt и user_prompt: отвечать строго на нужном языке
- Новый метод: generate_engineer_probability()
"""

import logging
from django.conf import settings
from openai import OpenAI
from pydantic import BaseModel

from apps.support.models import SupportTicket
from apps.translation._core.active_language_context import get_language


logger = logging.getLogger(__name__)

_client = OpenAI(api_key=settings.OPENAI_KEY)


# ============================================================
# STRICT JSON SCHEMAS
# ============================================================

class GlobalAdviceSchema(BaseModel):
    client_advice: str
    engineer_advice: str


class EngineerProbabilitySchema(BaseModel):
    probability: int
    explanation: str


# ============================================================
# MAIN CLASS
# ============================================================

class OpenAIUseCase:

    # ============================================================
    # STRICT JSON REQUEST
    # ============================================================
    @staticmethod
    def _request(system_prompt: str, user_text: str, schema, model: str = "gpt-4o-mini"):

        try:
            result = _client.beta.chat.completions.parse(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text},
                ],
                temperature=0.1,
                response_format=schema,
            )

            parsed = result.choices[0].message.parsed
            data = parsed.dict()

            # ---- Normalize Unicode ----
            def normalize(v):
                if isinstance(v, str):
                    return v.encode("utf-8").decode("utf-8")
                if isinstance(v, list):
                    return [normalize(x) for x in v]
                if isinstance(v, dict):
                    return {k: normalize(x) for k, x in v.items()}
                return v

            return normalize(data)

        except Exception:
            logger.exception("OpenAI strict JSON request failed")
            return None

    # ============================================================
    # GENERATE GLOBAL RECOMMENDATIONS
    # ============================================================
    @staticmethod
    def generate_global_recommendations(description: str):
        """
        Строгий JSON:
        {
            "client_advice": "...",
            "engineer_advice": "..."
        }
        """

        lang = get_language()  # 'ru', 'kk', 'en'
        lang_map = {"ru": "русском", "kk": "қазақ", "en": "English"}
        lang_human = lang_map.get(lang, "English")

        qs = SupportTicket.objects.exclude(final_resolution=None).exclude(final_resolution="")

        history_text = ""
        for t in qs.order_by("-created_at")[:30]:
            history_text += f"- {t.final_resolution}\n"
        if not history_text:
            history_text = "(финальные решения отсутствуют)"

        system_prompt = (
            "Ты — официальный AI-помощник службы технической поддержки "
            "АО «Казахтелеком».\n\n"

            "На основе описания новой проблемы и опыта прошлых финальных решений "
            "сформируй ДВЕ рекомендации STRICT JSON:\n\n"

            "1) client_advice — краткая, простая рекомендация клиенту.\n"
            "2) engineer_advice — техническая рекомендация инженеру.\n\n"

            f"ВАЖНО: Ответ строго на {lang_human} языке.\n\n"

            "Финальный ответ только JSON:\n"
            "{\n"
            "  \"client_advice\": \"...\",\n"
            "  \"engineer_advice\": \"...\"\n"
            "}\n"
        )

        user_prompt = (
            f"Описание новой проблемы:\n{description}\n\n"
            f"Прошлые финальные решения:\n{history_text}\n\n"
            f"Ответ строго на {lang_human} языке."
        )

        return OpenAIUseCase._request(
            system_prompt=system_prompt,
            user_text=user_prompt,
            schema=GlobalAdviceSchema,
        )

    # ============================================================
    # NEW: GENERATE ENGINEER VISIT PROBABILITY
    # ============================================================
    @staticmethod
    def generate_engineer_probability(description: str, age: int):
        """
        Строгий JSON:
        {
            "probability": 70,
            "explanation": "..."
        }

        Использует:
        - описание новой проблемы
        - возраст клиента
        - историю всех прошлых:
            - description
            - engineer_visit_probability
        """



        # ---- История прошлых вероятностей ----
        qs = SupportTicket.objects.exclude(engineer_visit_probability=None)

        history = ""
        for t in qs.order_by("-created_at")[:50]:
            history += (
                f"- Описание: {t.description}\n"
                f"  Вероятность вызова инженера: {t.engineer_visit_probability}\n\n"
            )
        if not history:
            history = "(данные отсутствуют)"

        # ---- System prompt ----
        system_prompt = (
            "Ты — аналитический AI-помощник технической поддержки АО «Казахтелеком».\n\n"
            "Твоя задача — определить вероятность необходимости вызова инженера на основе:\n"
            "- описания новой проблемы\n"
            "- возраста клиента\n"
            "- истории прошлых проблем и их engineer_visit_probability\n\n"

            "Правила:\n"
            "- анализируй похожие ситуации\n"
            "- если клиент пожилой (60+), вероятность должна быть выше, так как требуется помощь на месте\n"
            "- результат должен быть целым числом от 0 до 100\n"
            "- дай краткое объяснение\n\n"

            "Ответ только STRICT JSON:\n"
            "{\n"
            "  \"probability\": 0-100,\n"
            "  \"explanation\": \"...\"\n"
            "}\n"
        )

        # ---- User prompt ----
        user_prompt = (
            f"Описание новой проблемы:\n{description}\n\n"
            f"Возраст клиента: {age}\n\n"
            f"Прошлые заявки:\n{history}\n\n"
        )

        # ---- STRICT JSON ----
        return OpenAIUseCase._request(
            system_prompt=system_prompt,
            user_text=user_prompt,
            schema=EngineerProbabilitySchema,
        )
