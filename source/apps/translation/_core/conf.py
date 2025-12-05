"""
Language configuration for the web application.

Languages are defined by their code (e.g., "ru", "en", "kk").
The name is used only for UI display.
"""

from django.conf import settings


# === Core Settings ===

ENABLE_DJANGO_TRANSLATION_ACTIVATE: bool = False  # Enable django.utils.translation.activate(lang_code)
TRANSLATION_CACHE_TTL_SECONDS: int = 60 * 8       # Cache TTL in seconds


# === Language Roles ===

DEFAULT_LANGUAGE_STARTUP: str = "ru"              # Language used at startup if not provided
DEFAULT_REFERENCE_LANGUAGE: str = "ru"            # Reference (base) language for DB and templates
AUTO_COPY_REFERENCE_TEXT: bool = True             # Auto-copy source_text → default reference field if empty


# === URL Exclusions (no redirect to /<lang>/...) ===

LANGUAGE_EXCLUDED_URL_PREFIXES: list[str] = [
    "/api",
    "/dj-admin"
]


# === Supported Languages ===

SUPPORTED_LANGUAGES: list[dict[str, str | bool]] = [
    {"code": "ru", "name": "Русский", "visible_in_ui": True},
    {"code": "en", "name": "English", "visible_in_ui": True},
    {"code": "kk", "name": "Қазақша", "visible_in_ui": True},
]


# === Public API ===


def get_supported_language_codes() -> list[str]:
    """Return a list of supported language codes."""
    return [lang["code"] for lang in SUPPORTED_LANGUAGES]


def get_visible_languages() -> list[dict[str, str]]:
    """Return list of languages shown in UI selectors."""
    return [
        {"code": lang["code"], "name": lang["name"]}
        for lang in SUPPORTED_LANGUAGES
        if lang.get("visible_in_ui")
    ]


def get_language_name(lang_code: str) -> str:
    """Return the human-readable name of a language by code."""
    return next(
        (lang["name"] for lang in SUPPORTED_LANGUAGES if lang["code"] == lang_code),
        lang_code,
    )


def get_language_dict() -> dict[str, str]:
    """Return a dict of all supported languages with their names."""
    return {lang["code"]: lang["name"] for lang in SUPPORTED_LANGUAGES}


def is_openai_enabled() -> bool:
    """Return True if OpenAI translation is enabled via Django settings."""
    return bool(getattr(settings, "OPENAI_KEY", "").strip())


def validate_translation_config() -> None:
    """
    Validate configuration structure and values.

    Raises ValueError if:
    - DEFAULT_LANGUAGE_STARTUP or DEFAULT_REFERENCE_LANGUAGE are not in supported codes.
    - Missing "code" or "name" in language entries.
    - Duplicate language codes found.
    - Excluded paths do not start with "/".
    """
    codes = get_supported_language_codes()

    if DEFAULT_LANGUAGE_STARTUP not in codes:
        raise ValueError(
            f"DEFAULT_LANGUAGE_STARTUP ('{DEFAULT_LANGUAGE_STARTUP}') is not in SUPPORTED_LANGUAGES."
        )

    if DEFAULT_REFERENCE_LANGUAGE not in codes:
        raise ValueError(
            f"DEFAULT_REFERENCE_LANGUAGE ('{DEFAULT_REFERENCE_LANGUAGE}') is not in SUPPORTED_LANGUAGES."
        )

    seen = set()
    for lang in SUPPORTED_LANGUAGES:
        code = lang.get("code")
        name = lang.get("name")
        if not code or not name:
            raise ValueError(
                f"Each language must have 'code' and 'name'. Invalid entry: {lang}"
            )
        if code in seen:
            raise ValueError(f"Duplicate language code detected: '{code}'")
        seen.add(code)

    for path in LANGUAGE_EXCLUDED_URL_PREFIXES:
        if not path.startswith("/"):
            raise ValueError(f"Excluded path must start with '/': '{path}'")


# === Auto-validation on import ===

validate_translation_config()
