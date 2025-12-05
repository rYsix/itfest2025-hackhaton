from django.db import models

from ._core.conf import SUPPORTED_LANGUAGES


class Translation(models.Model):
    source_text = models.TextField(
        verbose_name="Source text",
        unique=True,
        db_index=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Last updated at",
    )

    class Meta:
        verbose_name = "Переводы"
        verbose_name_plural = "Переводы"
        ordering = ["source_text"]

    def __str__(self) -> str:
        return self.source_text or "[empty]"


for lang in SUPPORTED_LANGUAGES:
    Translation.add_to_class(
        f"text_{lang['code']}",
        models.TextField(
            verbose_name=f"Text in {lang['name']}",
            null=True,
            blank=True,
        ),
    )
