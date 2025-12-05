"""
hackaton_itfest_proj/logging.py
Custom logging config with DB logging handler.
"""

import logging
import traceback
from pathlib import Path
from logging.handlers import RotatingFileHandler  # noqa: F401
from django.conf import settings

# ==============================================================================
#  DIR SETUP
# ==============================================================================

LOG_DIR: Path = Path(getattr(settings, "LOG_DIR", settings.RUNTIME_DIR / "logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)

MAX_LOG_SIZE = 30 * 1024 * 1024
LOG_BACKUPS = 3

# ==============================================================================
#  DB HANDLER (no verbosity flag, minimal fields)
# ==============================================================================

class DbLogHandler(logging.Handler):
    """
    Writes log records into common.models.LogRecord.
    - Includes traceback if exception info exists.
    - Sanitizes and includes extra_data.
    """

    def emit(self, record: logging.LogRecord) -> None:
        try:
            from  apps.common.models import LogRecord  # avoid circular import

            traceback_text = ""
            if record.exc_info:
                traceback_text = self._format_exc(record.exc_info)
            elif getattr(record, "exc_text", None):
                traceback_text = record.exc_text

            raw_extra = getattr(record, "extra", None)
            extra_data = self._sanitize_extra(raw_extra) if raw_extra else None

            LogRecord.objects.create(
                level=record.levelname,
                message=record.getMessage(),
                logger_name=record.name or "",
                traceback=traceback_text,
                extra_data=extra_data or None,
            )

        except Exception as exc:
            fallback_logger = logging.getLogger("log_db_fallback")
            fallback_logger.exception("DbLogHandler failed: %s: %s", exc.__class__.__name__, exc)

    @staticmethod
    def _format_exc(exc_info):
        try:
            return "".join(traceback.format_exception(*exc_info))
        except Exception:
            return "<traceback format failed>"

    def _sanitize_extra(self, data):
        def process(val):
            if isinstance(val, (dict, list, str, int, float, bool, type(None))):
                return val
            if isinstance(val, type):
                return f"<Class: {val.__name__}>"
            if callable(val):
                return f"<Function: {getattr(val, '__name__', 'unknown')}>"
            try:
                return str(val)
            except Exception:
                return f"<Unserialisable: {type(val).__name__}>"

        def recurse(obj):
            if isinstance(obj, dict):
                return {str(k): recurse(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [recurse(i) for i in obj]
            return process(obj)

        try:
            return recurse(data)
        except Exception as exc:
            return {"_error": f"sanitize_failed: {exc.__class__.__name__}"}

# ==============================================================================
#  LOGGING CONFIG
# ==============================================================================

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,

    "filters": {
        "require_debug_true": {"()": "django.utils.log.RequireDebugTrue"},
    },

    "formatters": {
        "verbose": {
            "format": "%(asctime)s [%(levelname)s] %(name)s %(pathname)s:%(lineno)d\n%(message)s",
        },
        "simple": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        },
    },

    "handlers": {
        "error_file": {
            "level": "WARNING",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "errors.log",
            "formatter": "verbose",
            "maxBytes": MAX_LOG_SIZE,
            "backupCount": LOG_BACKUPS,
            "encoding": "utf-8",
        },
        "info_file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "info.log",
            "formatter": "simple",
            "maxBytes": MAX_LOG_SIZE,
            "backupCount": LOG_BACKUPS,
            "encoding": "utf-8",
        },
        "debug_mode_console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "simple",
            "filters": ["require_debug_true"],
        },
        "db_info": {
            "level": "INFO",
            "class": "hackaton_itfest_proj.logging.DbLogHandler",
        },
    },

    "loggers": {
        "django": {
            "handlers": ["info_file", "error_file", "debug_mode_console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.server": {
            "handlers": ["debug_mode_console"],
            "level": "INFO",
            "propagate": False,
        },
        "log_db_fallback": {
            "handlers": ["info_file", "error_file", "debug_mode_console"], #without db cuz of recursion
            "level": "ERROR",
            "propagate": False,
        },
        "httpcore":{
            "handlers": [],
            "level": "INFO",
            "propagate": False,
        },
        "openai":{
            "handlers": [],
            "level": "INFO",
            "propagate": False,
        },
        "httpx":{
            "handlers": [],
            "level": "INFO",
            "propagate": False,
        },
    },

    "root": {
        "handlers": ["info_file", "error_file", "debug_mode_console", "db_info"],
        "level": "DEBUG",
    },
}
