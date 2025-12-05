"""
In-memory cache for translation values (thread-safe, TTL-based).

Thread safety:
- The cache is a plain Python dictionary.
- All read/write operations are protected by threading.Lock to support
  concurrent Django request handling.

Time-to-live (TTL):
- Each item is stored with an expiration time defined by TRANSLATION_CACHE_TTL_SECONDS.
- Expired entries are lazily removed on access.

Usage:
- Cache key: (source_text, lang_code)
- Value: (translated_text, expires_at)

Notes:
- `source_text` is the unique base key in the DB.
- Supports caching translations for all languages, including the default reference language.
"""

import threading
import time

from .conf import TRANSLATION_CACHE_TTL_SECONDS

# (source_text, lang_code) → (translated_value, expires_at)
_cache: dict[tuple[str, str], tuple[str, float]] = {}
_cache_lock = threading.Lock()


def get_from_cache(key: str, lang_code: str) -> str | None:
    """
    Return a cached translation if present and not expired.

    :param key: Source text (unique DB value)
    :param lang_code: Target language code
    :return: Cached translation, or None if missing or expired
    """
    now = time.time()
    cache_key = (key, lang_code)

    with _cache_lock:
        item = _cache.get(cache_key)
        if not item:
            return None

        value, expires_at = item
        if now > expires_at:
            del _cache[cache_key]
            return None

        return value


def save_to_cache(key: str, lang_code: str, value: str) -> None:
    """
    Save a translation value in the cache with TTL.

    :param key: Source text (unique DB value)
    :param lang_code: Target language code
    :param value: Translated text
    """
    expires_at = time.time() + TRANSLATION_CACHE_TTL_SECONDS
    with _cache_lock:
        _cache[(key, lang_code)] = (value, expires_at)


def invalidate_cache() -> None:
    """Clear the entire translation cache."""
    with _cache_lock:
        _cache.clear()
