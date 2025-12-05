"""
CORE OpenAI JSON Helper.

Минимальный и чистый вариант:
- Static class OpenAIUseCase
- _request() → строгий JSON через Pydantic schema → ВСЕГДА dict
- example_usage() → тоже ВСЕГДА dict
"""

import logging
from django.conf import settings
from openai import OpenAI

logger = logging.getLogger(__name__)

_client = OpenAI(api_key=settings.OPENAI_KEY)


class OpenAIUseCase:
    # ============================================================
    # CORE PRIVATE METHOD (STRICT JSON, returns dict)
    # ============================================================

    @staticmethod
    def _request(system_prompt: str, user_text: str, schema, model: str = "gpt-4o-mini"):
        """
        Выполняет STRICT JSON запрос через Pydantic schema
        и возвращает ТОЛЬКО dict.

        Возвращает:
            dict — готовый JSON-объект
            None — ошибка
        """

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

            # ---- Convert Pydantic model → dict ----
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
    # PLACEHOLDER — ONLY RETURNS dict
    # ============================================================

    @staticmethod
    def example_usage(text: str):
        """
        Простейший тестовый метод.
        Возвращает ТОЛЬКО dict.
        """

        from pydantic import BaseModel

        class ExampleSchema(BaseModel):
            summary: str

        system_prompt = (
            "Сделай краткое описание текста. "
            "Ответ строго JSON:\n"
            "{ \"summary\": \"...\" }"
        )

        return OpenAIUseCase._request(
            system_prompt=system_prompt,
            user_text=text,
            schema=ExampleSchema,
        )
