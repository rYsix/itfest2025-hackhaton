from django import template
from django.urls import reverse
from django.utils.safestring import mark_safe

from .._core.active_language_context import get_language
from .._core.translator import get_translate

register = template.Library()


@register.simple_tag
def url(view_name: str, *args, **kwargs) -> str:
    """
    Build a language-prefixed URL using the active language.

    Example:
        {% url 'index' %}  →  /en/index
    """
    lang = get_language()
    base_url = reverse(view_name, args=args, kwargs=kwargs)
    return f"/{lang}{base_url}"


@register.simple_tag
def tr(key: str, force: bool = False) -> str:
    """
    Translate a string key into the current active language.

    :param key: Source text (unique in DB).
    :param force:
        - True → always resolve translation, even if current language
          is the default reference language.
        - False → return key as-is when current language == default.

    The result is marked safe for HTML rendering.

    Examples:
        {% tr "Submit" %}       → respects default language shortcut
        {% tr "Submit" True %}  → forces translation lookup
    """
    try:
        return mark_safe(get_translate(key, is_default_lang=not force))
    except Exception as exc:
        return f"[translation error: {exc}]"
