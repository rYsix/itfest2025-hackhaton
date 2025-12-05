"""
CORE OpenAI JSON Helper + Ticket AI Resolver (Unified).

Особенности:
- Автоматический выбор языка клиента через get_language()
- Переводится только client_advice
- Все тех. тексты (engineer_advice, объяснения) всегда на русском
- Один AI-запрос → полный JSON
- Жёсткое ограничение предметной области: ТОЛЬКО услуги Казахтелекома
- Классификатор «телеком / не телеком»
- <<< NEW >>> Запрет на любые фразы «позвоните нам», «обратитесь в поддержку»
- <<< NEW >>> Мы уже техподдержка: не перенаправлять клиента
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
# STRICT JSON SCHEMA
# ============================================================

class FullAISchema(BaseModel):
    client_advice: str
    engineer_advice: str
    engineer_probability: int
    engineer_probability_explanation: str
    initial_priority: int


class TelecomCheckSchema(BaseModel):
    is_telecom: bool


# ============================================================
# MAIN CLASS
# ============================================================

class OpenAIUseCase:

    # ------------------------------------------------------------
    # BASE STRICT CALL
    # ------------------------------------------------------------
    @staticmethod
    def _request(system_prompt: str, user_text: str, schema, model: str = "gpt-4o-mini"):
        try:
            result = _client.beta.chat.completions.parse(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_text},
                ],
                temperature=0.1,
                response_format=schema,
            )
            return result.choices[0].message.parsed.dict()
        except Exception:
            logger.exception("OpenAI strict JSON request failed")
            return None


    # ============================================================
    # <<< NEW >>> TELECOM CLASSIFIER
    # ============================================================
    @staticmethod
    def classify_telecom_issue(description: str) -> bool:
        """
        True → проблема относится к телеком
        False → не наша зона ответственности
        """

        system_prompt = (
            "Ты — строгий классификатор технической поддержки Казахтелекома.\n"
            "Твоя задача — определить, относится ли проблема к телеком-услугам.\n\n"

            "Телеком-сфера включает:\n"
            " - домашний и корпоративный интернет (FTTH, GPON, xDSL)\n"
            " - Wi-Fi, маршрутизаторы, ONU/ONT\n"
            " - IPTV и TV-приставки\n"
            " - IP-телефонию, SIP, VoIP\n"
            " - мобильную связь 4G/5G\n"
            " - проводную телефонию\n\n"

            "НЕ относится:\n"
            " - автомобили, двигатель, ремонт техники\n"
            " - компьютеры / ноутбуки как устройство\n"
            " - медицина, здоровье\n"
            " - сантехника, электрика, стройка\n"
            " - бытовая техника, кондиционеры, плиты\n\n"

            "Ответ строго JSON:\n"
            "{ \"is_telecom\": true }\n"
            "или\n"
            "{ \"is_telecom\": false }\n"
        )

        user_prompt = f"Описание проблемы:\n{description}\nВерни только JSON."

        result = OpenAIUseCase._request(
            system_prompt=system_prompt,
            user_text=user_prompt,
            schema=TelecomCheckSchema,
        )

        return bool(result and result.get("is_telecom", False))


    # ============================================================
    # UNIFIED TICKET AI
    # ============================================================
    @staticmethod
    def generate_full_ticket_ai(description: str, age: int):

        # Язык для client_advice
        lang = get_language()
        lang_human = {"ru": "русском", "kk": "қазақ", "en": "English"}.get(lang, "English")

        # Истории
        hist_res = "\n".join([
            f"- {t.final_resolution}"
            for t in SupportTicket.objects.exclude(final_resolution=None).exclude(final_resolution="")
            .order_by("-created_at")[:30]
        ]) or "(нет данных)"

        hist_prob = "\n".join([
            f"- {t.description}\n  Вероятность: {t.engineer_visit_probability}"
            for t in SupportTicket.objects.exclude(engineer_visit_probability=None)
            .order_by("-created_at")[:40]
        ]) or "(нет данных)"

        # ============================================================
        # SYSTEM PROMPT — САМЫЙ ЖЁСТКИЙ
        # ============================================================
        system_prompt = (
            "Ты — единая AI-система технической поддержки АО «Казахтелеком». "
            "Ты уже являешься службой поддержки. "
            "Поэтому ЗАПРЕЩЕНО говорить пользователю:\n"
            " - «позвоните нам»\n"
            " - «обратитесь в поддержку»\n"
            " - «создайте заявку»\n"
            " - «перезвоните оператору»\n"
            " - «обратитесь к специалисту»\n"
            " - любые другие просьбы позвонить\n\n"

            "Ты НЕ должен перенаправлять клиента. Ты — последний и конечный оператор.\n\n"

            "------------------------------------------------------------\n"
            "   ПРОБЛЕМЫ НЕ ТЕЛЕКОМ — ЗАПРЕЩЕНО ДАВАТЬ ЛЮБЫЕ СОВЕТЫ\n"
            "------------------------------------------------------------\n"
            "Если проблема не относится к телеком, ты ДОЛЖЕН вернуть JSON:\n"
            "{\n"
            f'  "client_advice": "Вы описали проблему, которая не относится к услугам Казахтелекома.",\n'
            '  "engineer_advice": "",\n'
            '  "engineer_probability": 0,\n'
            '  "engineer_probability_explanation": "",\n'
            '  "initial_priority": 30\n'
            "}\n\n"
            "БЕЗ любых дополнительных советов.\n"
            "Никаких бытовых рекомендаций («попробуйте», «почистите», «перезагрузите»).\n\n"

            "------------------------------------------------------------\n"
            "   ЕСЛИ ПРОБЛЕМА ТЕЛЕКОМ — ГЕНЕРИРУЙ РЕАЛЬНЫЕ ДЕЙСТВИЯ\n"
            "------------------------------------------------------------\n"
            "client_advice — короткая безопасная рекомендация, переводить на язык клиента.\n"
            "engineer_advice — технические шаги для инженера, строго по-русски.\n"
            "engineer_probability — оценка необходимости выезда.\n"
            "initial_priority — 30–70.\n\n"

            "Вернуть только JSON. Без markdown. Не объясняй правила."
        )

        # ============================================================
        # USER PROMPT
        # ============================================================
        user_prompt = (
            f"Описание проблемы:\n{description}\n\n"
            f"Возраст клиента: {age}\n\n"
            f"История финальных решений:\n{hist_res}\n\n"
            f"История engineer_probability:\n{hist_prob}\n\n"
            f"client_advice на {lang_human} языке.\n"
            "Остальные поля — строго по-русски.\n"
            "Верни только JSON."
        )

        return OpenAIUseCase._request(
            system_prompt=system_prompt,
            user_text=user_prompt,
            schema=FullAISchema,
        )
