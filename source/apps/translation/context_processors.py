"""
Django context processor for language-related variables.

Purpose:
- Expose the current language and available UI languages to all templates.
- Provide a clean path without the /<lang>/ prefix for language switching.
"""

from ._core.active_language_context import get_language
from ._core.conf import (
    get_visible_languages,
    get_supported_language_codes,
    get_language_name,
)


def current_language(request) -> dict:
    """
    Build a language context dictionary for templates.

    :param request: Django request object
    :return: dict with:
        - current_lang_code: e.g. "kk"
        - current_lang_name: e.g. "Қазақша"
        - current_path_without_lang: request path without /<lang>/ prefix
        - show_languages_extended: list of visible languages for UI
    """
    codes = get_supported_language_codes()
    lang_code = get_language()

    path_parts = request.path.strip("/").split("/")
    if path_parts and path_parts[0] in codes:
        trimmed_path = "/" + "/".join(path_parts[1:])
    else:
        trimmed_path = request.path or "/"

    query_string = request.META.get("QUERY_STRING")
    if query_string:
        trimmed_path += f"?{query_string}"

    return {
        "current_lang_code": lang_code,
        "current_lang_name": get_language_name(lang_code),
        "current_path_without_lang": trimmed_path,
        "show_languages_extended": get_visible_languages(),
    }
