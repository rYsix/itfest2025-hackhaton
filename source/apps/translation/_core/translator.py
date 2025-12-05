import logging
import queue
import threading
import time

from django.core.cache import cache

from .active_language_context import get_language
from .cache import get_from_cache, save_to_cache
from .conf import (
    DEFAULT_REFERENCE_LANGUAGE,
    AUTO_COPY_REFERENCE_TEXT,
    is_openai_enabled,
)
from .openai import generate_translation
from ..models import Translation

logger = logging.getLogger("data.translation.translator")

# ============================
# Queue and worker state
# ============================

_task_queue: queue.Queue = queue.Queue()
_pending_tasks: set[tuple[str, str]] = set()
_pending_lock = threading.Lock()

WORKER_COUNT = 4
REQUEST_DELAY = 1.2
CACHE_TTL = 30


# ============================
# Pending flag helpers
# ============================

def _make_task_key(source_text: str, lang_code: str) -> str:
    """
    Build cache key for translation pending flag.
    """
    return f"translation-pending:{lang_code}:{hash(source_text)}"


def mark_translation_pending(
    source_text: str,
    lang_code: str,
    ttl: int = CACHE_TTL,
) -> bool:
    key = _make_task_key(source_text, lang_code)
    if cache.get(key) is None:
        cache.set(key, "1", timeout=ttl)
        return True
    return False


def clear_translation_pending(source_text: str, lang_code: str) -> None:
    cache.delete(_make_task_key(source_text, lang_code))


# ============================
# Worker loop
# ============================

def _worker_loop() -> None:
    while True:
        try:
            source_text, lang_code, obj_id = _task_queue.get()
            try:
                time.sleep(REQUEST_DELAY)

                obj = Translation.objects.get(id=obj_id)
                obj.refresh_from_db()

                # already filled
                if getattr(obj, f"text_{lang_code}", None):
                    continue

                generated = generate_translation(source_text, lang_code)

                if generated:
                    setattr(obj, f"text_{lang_code}", generated)
                    obj.save(update_fields=[f"text_{lang_code}"])
                    save_to_cache(source_text, lang_code, generated)
                    logger.debug(
                        "Background translated | text='%s' | lang='%s'",
                        source_text,
                        lang_code,
                    )
                else:
                    save_to_cache(source_text, lang_code, source_text)
                    logger.warning(
                        "No usable translation | text='%s' | lang='%s'",
                        source_text,
                        lang_code,
                    )

            except Exception as e:
                logger.warning(
                    "Worker failed task | text='%s' | lang='%s' | error=%s",
                    source_text,
                    lang_code,
                    e,
                )
            finally:
                clear_translation_pending(source_text, lang_code)
                with _pending_lock:
                    _pending_tasks.discard((source_text, lang_code))
                _task_queue.task_done()

        except Exception:
            continue


# ============================
# Worker initialization
# ============================

_workers_started = False


def _start_workers() -> None:
    global _workers_started
    if not _workers_started:
        for _ in range(WORKER_COUNT):
            threading.Thread(target=_worker_loop, daemon=True).start()
        _workers_started = True


# ============================
# Public API
# ============================

def get_translate(
    source_text: str,
    is_default_lang: bool = True,
    fast: bool = True,
) -> str:

    lang_code = get_language()
    if not lang_code:
        raise RuntimeError("Language context not initialized via set_language().")

    # ------------------------------
    # Reference language
    # ------------------------------
    if lang_code == DEFAULT_REFERENCE_LANGUAGE and is_default_lang:
        obj, _ = Translation.objects.get_or_create(source_text=source_text)
        ref_field = f"text_{DEFAULT_REFERENCE_LANGUAGE}"

        if AUTO_COPY_REFERENCE_TEXT and not getattr(obj, ref_field, None):
            setattr(obj, ref_field, source_text)
            obj.save(update_fields=[ref_field])

        return source_text

    # ------------------------------
    # Cache
    # ------------------------------
    cached = get_from_cache(source_text, lang_code)
    if cached:
        return cached

    # ------------------------------
    # Database
    # ------------------------------
    obj, _ = Translation.objects.get_or_create(source_text=source_text)
    value = getattr(obj, f"text_{lang_code}", None)

    if value:
        save_to_cache(source_text, lang_code, value)
        return value

    # ------------------------------
    # OpenAI
    # ------------------------------
    if is_openai_enabled():

        # Fast mode → background
        if fast:
            _start_workers()

            task_key = (source_text, lang_code)

            with _pending_lock:
                if task_key not in _pending_tasks:
                    if mark_translation_pending(source_text, lang_code):
                        _pending_tasks.add(task_key)
                        _task_queue.put((source_text, lang_code, obj.id))
                        logger.debug(
                            "Task queued | text='%s' | lang='%s'",
                            source_text,
                            lang_code,
                        )
                else:
                    logger.debug(
                        "Duplicate task skipped | text='%s' | lang='%s'",
                        source_text,
                        lang_code,
                    )

            return source_text

        # Slow mode → blocking
        try:
            generated = generate_translation(source_text, lang_code)

            if generated:
                setattr(obj, f"text_{lang_code}", generated)
                obj.save(update_fields=[f"text_{lang_code}"])
                save_to_cache(source_text, lang_code, generated)
                return generated

            save_to_cache(source_text, lang_code, source_text)
            logger.warning(
                "Generated empty translation | text='%s' | lang='%s'",
                source_text,
                lang_code,
            )
            return source_text

        except Exception as e:
            logger.warning(
                "Translation failed | text='%s' | lang='%s' | error=%s",
                source_text,
                lang_code,
                e,
            )
            save_to_cache(source_text, lang_code, source_text)

    # ------------------------------
    # Fallback
    # ------------------------------
    return source_text
