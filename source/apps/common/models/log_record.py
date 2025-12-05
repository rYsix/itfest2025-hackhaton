from django.db import models


class LogRecord(models.Model):
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата и время записи",
        help_text="Момент создания записи в журнале логов."
    )
    level = models.CharField(
        max_length=10,
        verbose_name="Уровень",
        help_text="Уровень важности записи (например: INFO, ERROR, WARNING)."
    )
    message = models.TextField(
        verbose_name="Сообщение",
        help_text="Основной текст лог-записи."
    )
    logger_name = models.CharField(
        max_length=255,
        default="unknown",
        verbose_name="Имя логгера",
        help_text="Имя или источник, откуда пришло сообщение."
    )
    traceback = models.TextField(
        blank=True,
        verbose_name="Трассировка ошибки",
        help_text="Полная трассировка исключения, если применимо."
    )
    extra_data = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Дополнительные данные",
        help_text="Дополнительные параметры, переданные в лог (формат JSON)."
    )

    class Meta:
        verbose_name = "Запись лога"
        verbose_name_plural = "Журнал логов"
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.level}] {self.logger_name} — {self.message[:80]}"
