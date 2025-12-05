# apps/common/admin.py
from django.contrib import admin
from .models import LogRecord, CustomUser
from django.contrib.auth.admin import UserAdmin

@admin.register(LogRecord)
class LogRecordAdmin(admin.ModelAdmin):
    list_display = ("created_at", "level", "logger_name", "short_message")
    list_filter = ("level", "logger_name", "created_at")
    search_fields = ("message", "logger_name")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)

    def short_message(self, obj):
        return (obj.message[:100] + "...") if len(obj.message) > 100 else obj.message
    short_message.short_description = "Сообщение"


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ("id", "email", "full_name", "is_active", "is_staff")
    list_filter = ("is_active", "is_staff")
    ordering = ("id",)
    search_fields = ("email", "full_name")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Персональная информация", {"fields": ("full_name",)}),
        ("Права доступа", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Системная информация", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "full_name", "password1", "password2", "is_active", "is_staff"),
        }),
    )
