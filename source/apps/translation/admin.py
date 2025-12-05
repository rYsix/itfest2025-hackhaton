import csv

from django.http import HttpResponse
from django.contrib import admin
from django.conf import settings

from .models import Translation
from ._core.conf import SUPPORTED_LANGUAGES


@admin.register(Translation)
class TranslationAdmin(admin.ModelAdmin):
    """
    Admin interface for the Translation model.

    Features:
    - Dynamic list/search fields based on supported languages.
    - Limited list display for readability.
    - Source text readonly in production.
    - CSV export action for selected records.
    """

    base_list_display = ["id", "source_text", "updated_at"]
    base_search_fields = ["id", "source_text"]
    language_fields = [f"text_{lang['code']}" for lang in SUPPORTED_LANGUAGES]

    list_display = base_list_display + language_fields
    search_fields = base_search_fields + language_fields
    list_filter = ["updated_at"]
    ordering = ["-updated_at"]
    actions = ["export_as_csv"]

    def get_list_display(self, request):
        return self.base_list_display + self.language_fields[:4]

    def get_readonly_fields(self, request, obj=None):
        readonly = super().get_readonly_fields(request, obj)
        if not settings.DEBUG:
            return readonly + ("source_text",)
        return readonly

    @admin.action(description="Export selected translations as CSV")
    def export_as_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = "attachment; filename=translations.csv"

        writer = csv.writer(response)
        headers = ["ID", "Source text"] + [
            f"Text {lang['code']}" for lang in SUPPORTED_LANGUAGES
        ]
        writer.writerow(headers)

        for obj in queryset:
            row = [obj.id, obj.source_text] + [
                getattr(obj, field, "") for field in self.language_fields
            ]
            writer.writerow(row)

        return response
