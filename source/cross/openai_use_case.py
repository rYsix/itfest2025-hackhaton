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
- <<< NEW >>> AI выбор оптимального инженера под заявку
- <<< NEW >>> Tier-1 простой бот-ответ (строка)
"""

import logging
from django.conf import settings
from openai import OpenAI
from pydantic import BaseModel

from apps.support.models import SupportTicket, Engineer
from apps.translation._core.active_language_context import get_language

import re


logger = logging.getLogger(__name__)
_client = OpenAI(api_key=settings.OPENAI_KEY)


# ============================================================
# STRICT JSON SCHEMAS
# ============================================================

class FullAISchema(BaseModel):
    client_advice: str
    engineer_advice: str
    engineer_probability: int
    engineer_probability_explanation: str
    initial_priority: int

class MailSupportCheckSchema(BaseModel):
    is_support_request: bool
    reason: str


class TelecomCheckSchema(BaseModel):
    is_telecom: bool


class EngineerPickSchema(BaseModel):
    engineer_id: int
    engineer_name: str
    reason: str
    confidence: int


# ============================================================
# MAIN CLASS
# ============================================================

class OpenAIUseCase:

    # ------------------------------------------------------------
    # BASE STRICT CALL
    # ------------------------------------------------------------
    @staticmethod
    def _request(system_prompt: str, user_text: str, schema, model: str = "gpt-4o-mini"):
        """
        Унифицированный строгий JSON-запрос.
        """
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
        lang_human = {
            "ru": "русском",
            "kk": "қазақ",
            "en": "English"
        }.get(lang, "English")

        # Истории
        hist_res = "\n".join([
            f"- {t.final_resolution}"
            for t in SupportTicket.objects.exclude(final_resolution=None)
                                          .exclude(final_resolution="")
                                          .order_by("-created_at")[:30]
        ]) or "(нет данных)"

        hist_prob = "\n".join([
            f"- {t.description}\n  Вероятность: {t.engineer_visit_probability}"
            for t in SupportTicket.objects.exclude(engineer_visit_probability=None)
                                          .order_by("-created_at")[:40]
        ]) or "(нет данных)"

        # SYSTEM PROMPT
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

            "Ты НЕ должен перенаправлять клиента. Ты — последний оператор.\n\n"

            "Если проблема не относится к телеком — верни JSON:\n"
            "{\n"
            f'  "client_advice": "Вы описали проблему, которая не относится к услугам Казахтелекома.",\n'
            '  "engineer_advice": "",\n'
            '  "engineer_probability": 0,\n'
            '  "engineer_probability_explanation": "",\n'
            '  "initial_priority": 30\n'
            "}\n\n"

            "Если проблема телеком — генерируй реальные действия.\n"
            "client_advice — переводить на язык клиента.\n"
            "engineer_advice — строго по-русски.\n"
            "Верни только JSON."
        )

        user_prompt = (
            f"Описание проблемы:\n{description}\n\n"
            f"Возраст клиента: {age}\n\n"
            f"История финальных решений:\n{hist_res}\n\n"
            f"История engineer_probability:\n{hist_prob}\n\n"
            f"client_advice на {lang_human} языке.\n"
            "Верни только JSON."
        )

        return OpenAIUseCase._request(
            system_prompt=system_prompt,
            user_text=user_prompt,
            schema=FullAISchema,
        )

    # ============================================================
    # <<< NEW >>> AI ENGINEER PICKER
    # ============================================================
    @staticmethod
    def pick_engineer_for_ticket(ticket: SupportTicket):

        engineers = list(Engineer.objects.filter(is_active=True))
        if not engineers:
            return None

        engineers_payload = []
        for e in engineers:
            engineers_payload.append({
                "id": e.id,
                "name": e.full_name,
                "active_tickets": e.supportticket_set.filter(
                    status__in=["new", "in_progress"]
                ).count(),
                "solved_descriptions": list(
                    SupportTicket.objects.filter(engineer=e, status="done")
                    .values_list("description", flat=True)[:25]
                ),
            })

        system_prompt = (
            "Ты — система распределения инженеров Казахтелекома.\n"
            "Выбери оптимального инженера.\n"
            "Верни только JSON.\n"
        )

        user_prompt = (
            f"Описание проблемы: {ticket.description}\n\n"
            f"Возраст клиента: {ticket.client.age}\n\n"
            f"Инженеры и их история: {engineers_payload}\n\n"
            "Выбери инженера."
        )

        return OpenAIUseCase._request(
            system_prompt=system_prompt,
            user_text=user_prompt,
            schema=EngineerPickSchema
        )

    # ============================================================
    # <<< UPDATED >>> TIER-1 SIMPLE SUPPORT BOT WITH HISTORY
    # ============================================================
    @staticmethod
    def tier1_support_reply(message: str, history: list | None = None) -> str:
        """
        Tier-1 поддержка Казахтелекома.
        Теперь учитывает историю переписки.

        history = [
            {"role": "user", "text": "..."},
            {"role": "assistant", "text": "..."},
            ...
        ]
        """

        lang = get_language() or "ru"

        # ================================================================
        # FULL INTELLIGENT SYSTEM PROMPTS
        # ================================================================
        system_prompts = {
            "ru": (
                "Ты — специалист линии технической поддержки №1 Казахтелекома (Tier-1).\n"
                "Главная цель — быстро дать короткий практичный совет, который пользователь может выполнить сам.\n"
                "Пиши кратко: 1–3 предложения. Стиль спокойный, уверенный.\n\n"

                "Разрешено:\n"
                "- давать простые шаги: проверить кабель, питание, перезагрузить ONU/ONT, роутер;\n"
                "- подсказать про индикаторы (PON, LOS, Internet);\n"
                "- рекомендации по Wi-Fi (канал, перегрев, интерференция);\n"
                "- проверить работу на прямом кабеле.\n\n"

                "Запрещено:\n"
                "- упоминать контакт-центр, номера телефонов, офисы;\n"
                "- просить позвонить куда-либо;\n"
                "- делать длинные объяснения;\n"
                "- давать инженерные термины 2-го уровня.\n\n"

                "Когда можно предложить эскалацию:\n"
                "- если нет сигнала PON или постоянно мигает LOS;\n"
                "- если ONU не включается, пахнет гарью, повреждён кабель;\n"
                "- если интернет полностью отсутствует и проблема явно физическая.\n"
                "Формулировка эскалации всегда одна: «Если проблема сохраняется — оставьте заявку на сайте AqylNet.kz».\n\n"

                "Отвечай только по существу, 1–3 предложения."
            ),

            "kk": (
                "Сен — «Қазақтелеком» компаниясының 1-деңгейлі техникалық қолдау маманысың (Tier-1).\n"
                "Мақсат — қолданушы өзі тексере алатын қысқа әрі нақты кеңес беру.\n"
                "Ұзындығы: 1–3 сөйлем.\n\n"

                "Эскалация тек мына жағдайда рұқсат:\n"
                "- PON жанбайды немесе LOS жыпылықтай береді;\n"
                "- құрылғы мүлдем қосылмайды;\n"
                "- физикалық ақау бар.\n"
                "Фраза өзгермейді: «Мәселе шешілмесе — AqylNet.kz сайтында өтінім қалдырыңыз».\n\n"

                "Өте қысқа, нақты жауап қайтар."
            ),

            "en": (
                "You are Tier-1 support of Kazakhtelecom.\n"
                "Your task: give a short, practical, user-friendly tip in 1–3 sentences.\n"
                "Allowed: checking cables, rebooting ONU, LED indicators, simple Wi-Fi tips.\n"
                "Forbidden: telling user to call somewhere, long complex explanations.\n\n"
                "Escalation phrase must be: “If the issue remains, please leave a request on AqylNet.kz”.\n"
                "Respond briefly."
            ),
        }

        system_prompt = system_prompts.get(lang, system_prompts["ru"])

        # ================================================================
        # BUILD MESSAGE LIST WITH HISTORY
        # ================================================================
        messages = [{"role": "system", "content": system_prompt}]

        # История: нормализуем (безопасно)
        if history:
            for h in history:
                if h.get("role") in ["user", "assistant"]:
                    messages.append({"role": h["role"], "content": h.get("text", "")})

        # Текущее сообщение
        messages.append({"role": "user", "content": message})

        # ================================================================
        # OPENAI REQUEST
        # ================================================================
        try:
            response = _client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.25,
                messages=messages
            )
            return response.choices[0].message.content.strip()

        except Exception:
            logger.exception("Tier1 reply failed")

            fallback = {
                "kk": "Қате орын алды. Қайта көріңіз.",
                "en": "Temporary error. Please try again.",
                "ru": "Произошла ошибка. Попробуйте ещё раз."
            }
            return fallback.get(lang, fallback["ru"])
        
        
    # ============================================================
    # <<< NEW >>> MAIL → TELECOM SUPPORT AI CHECK
    # ============================================================
    @staticmethod
    def ai_check_telecom_support_mail(subject: str, description: str) -> bool:
        """
        True — если письмо:
        - является обращением в техподдержку Казахтелеком
        - содержит ФИО клиента
        - содержит лицевой счёт
        False — во всех остальных случаях
        """

        if not subject or not description:
            return False

        system_prompt = (
            "Ты — строгий AI-классификатор службы технической поддержки "
            "АО «Казахтелеком».\n\n"

            "Твоя задача — определить, ЯВЛЯЕТСЯ ли письмо полноценным "
            "обращением в техническую поддержку.\n\n"

            "Верни TRUE только если одновременно выполнены ВСЕ условия:\n"
            "1. Клиент обращается именно по вопросам телеком-услуг "
            "(интернет, GPON, Wi-Fi, ONU/ONT, IPTV, связь и т.д.).\n"
            "2. В тексте письма присутствует ФИО клиента (любая естественная форма).\n"
            "3. В тексте письма явно присутствует лицевой счёт клиента.\n\n"

            "Если хотя бы одно условие не выполнено — верни FALSE.\n\n"

            "❌ НЕ пытайся угадывать\n"
            "❌ НЕ будь либеральным\n"
            "✅ Если есть сомнение — False\n\n"

            "Верни СТРОГО JSON:\n"
            "{\n"
            "  \"is_support_request\": true | false,\n"
            "  \"reason\": \"краткое объяснение\"\n"
            "}"
        )

        user_prompt = (
            f"ТЕМА ПИСЬМА:\n{subject}\n\n"
            f"ТЕКСТ ПИСЬМА:\n{description}\n\n"
            "Проанализируй и верни только JSON."
        )

        result = OpenAIUseCase._request(
            system_prompt=system_prompt,
            user_text=user_prompt,
            schema=MailSupportCheckSchema,
        )

        if not result:
            return False

        logger.info(
            "Mail AI support check: %s | reason=%s",
            result["is_support_request"],
            result["reason"]
        )

        return bool(result.get("is_support_request"))
