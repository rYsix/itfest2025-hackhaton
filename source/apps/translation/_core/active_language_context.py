"""
Manage the active language context for the current request (sync/async safe).

Purpose:
- Language is set once at the start of request handling (typically in middleware).
- It is stored in a ContextVar (isolated per task/context).
- This allows calling get_language() without passing the request object.

Note:
- This is not a global language state — each request/task has its own.
"""

from contextvars import ContextVar

from .conf import get_supported_language_codes, DEFAULT_LANGUAGE_STARTUP

_lang_ctx: ContextVar[str | None] = ContextVar("lang_code", default=None)
_valid_codes = set(get_supported_language_codes())


def set_language(lang_code: str) -> None:
    """
    Set the active language code for the current request context.

    Should be called early, typically in middleware.

    :param lang_code: Valid language code, e.g. "en".
    :raises ValueError: If lang_code is not in the supported list.
    """
    if lang_code not in _valid_codes:
        raise ValueError(
            f"Invalid language code '{lang_code}'. "
            f"Must be one of: {', '.join(sorted(_valid_codes))}"
        )
    _lang_ctx.set(lang_code)


def get_language() -> str:
    """
    Get the current language code for this request context.

    Falls back to DEFAULT_LANGUAGE_STARTUP if not set.
    """
    lang = _lang_ctx.get()
    return lang if lang is not None else DEFAULT_LANGUAGE_STARTUP
