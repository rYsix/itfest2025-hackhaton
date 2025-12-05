"""
OpenAI-based translation generator using GPT models.

Features:
- Auto-detects source language.
- Generates 10 translation candidates (5 literal + 5 dictionary-guided).
- Retries candidate generation up to N times if incomplete.
- Selects the best candidate using evaluation prompt.
- Returns plain translated string (no quality threshold).
"""

from django.conf import settings
from openai import OpenAI
from pydantic import BaseModel

from .conf import get_language_dict, is_openai_enabled


# ============================
# Schemas
# ============================


class CandidatesSchema(BaseModel):
    """Schema for candidate translations."""
    translations: list[str]


class BestSchema(BaseModel):
    """Schema for best translation selection."""
    best: str


# ============================
# Prompts
# ============================


def _build_candidates_prompt(lang_name: str) -> str:
    """
    Build a system prompt for candidate translation generation.

    Produces 10 translations:
    - First 5: literal, UI-suitable.
    - Next 5: dictionary-based (canonical wording).
    """
    return (
        f"You are a professional translator working on a GAME BOOSTING WEBSITE. "
        f"This is a commercial web application where accuracy, consistency, and semantic fidelity are critical.\n\n"
        f"--- TASK ---\n"
        f"1. Auto-detect the source language.\n"
        f"2. Translate the given text into {lang_name}.\n"
        f"3. Generate exactly 10 translation candidates:\n"
        f"   - First 5: literal and interface-appropriate translations.\n"
        f"   - Next 5: dictionary-style translations (from Oxford, Cambridge, Multitran, Glosbe) "
        f"using canonical wordings.\n\n"
        f"--- RULES ---\n"
        f"- Output must be strict JSON with a single key 'translations', containing a list of 10 plain strings.\n"
        f"- No formatting, no explanations, no comments — just raw JSON.\n"
        f"- Preserve all placeholders ({{}}, %s, {{variable}}), numbers, emojis, HTML tags.\n"
        f"- Retain gaming terms exactly:\n"
        f"   booster → 'booster' (EN), 'бустер' (RU/KZ)\n"
        f"   boosting → 'бустинг'\n"
        f"   rank → 'ранг'\n"
        f"- Do not replace gaming terms with synonyms (e.g., 'helper', 'accelerator').\n"
        f"- Do not shorten or simplify the meaning unless the source string itself is short.\n"
        f"- All legal, policy-related, or contractual texts must be translated with full accuracy and attention to detail.\n"
        f"- Maintain consistent terminology across all translations.\n"
    )


def _build_best_prompt(lang_name: str) -> str:
    """
    Build a system prompt for translation evaluation.

    Selects the single best translation from the 10 candidates.
    """
    return (
        f"You are a translation evaluator for a GAME BOOSTING WEBSITE.\n\n"
        f"--- TASK ---\n"
        f"You will receive 10 candidate translations into {lang_name}.\n"
        f"Your job is to select the single best translation.\n\n"
        f"--- EVALUATION CRITERIA ---\n"
        f"- Literal accuracy of meaning (no omissions or simplifications).\n"
        f"- Correct usage in the context of commercial UI and gaming terminology.\n"
        f"- Terminological fidelity: booster, boosting, rank, etc., must remain unchanged in form and meaning.\n"
        f"- No interpretation, rewriting, softening, or rephrasing allowed.\n"
        f"- Legal and policy-related text must be translated with complete clarity and precision.\n"
        f"- Short original phrases (e.g. 'Login') may be translated concisely (e.g. 'Вход') if fully accurate.\n"
        f"- Preserve all placeholders, emojis, HTML tags, and structure.\n"
        f"- If multiple options are equally valid, choose the most widely accepted and dictionary-consistent.\n\n"
        f"--- OUTPUT ---\n"
        f"Return strict JSON with one field: 'best'. "
        f"The value must be only the plain translation string. "
        f"No explanations, no prefixes, no formatting — just one string."
    )


# ============================
# Main logic
# ============================


def generate_translation(
    text: str,
    lang_code: str,
    max_retries: int = 3,
) -> str | None:
    """
    Generate a translation for the given text.

    Workflow:
    1. Generate 10 candidates (5 literal, 5 dictionary-based).
    2. Retry up to `max_retries` times if not enough candidates.
    3. Let GPT evaluate and select the best one.
    4. Return the best plain translation string.
    """
    if not is_openai_enabled():
        raise RuntimeError("OpenAI translation is disabled or API key is missing.")

    lang_name = get_language_dict().get(lang_code, lang_code)
    client = OpenAI(api_key=settings.OPENAI_KEY)
    translations: list[str] | None = None

    for attempt in range(1, max_retries + 1):
        candidates_result = client.beta.chat.completions.parse(
            model="gpt-4o-2024-11-20",
            messages=[
                {"role": "system", "content": _build_candidates_prompt(lang_name)},
                {"role": "user", "content": text},
            ],
            temperature=0.7,
            response_format=CandidatesSchema,
        )
        translations = candidates_result.choices[0].message.parsed.translations

        if translations and len(translations) == 10:
            break
        translations = None

    if not translations:
        return None

    options_text = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(translations))

    best_result = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": _build_best_prompt(lang_name)},
            {"role": "user", "content": options_text},
        ],
        temperature=0,
        response_format=BestSchema,
    )

    return best_result.choices[0].message.parsed.best.strip()
