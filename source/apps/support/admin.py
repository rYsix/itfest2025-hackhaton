from django.contrib import admin
from .models import (
    Client,
    Service,
    ClientService,
    Engineer,
    SupportTicket,
)


# ============================================================
# Inline: услуги клиента внутри карточки клиента
# ============================================================

class ClientServiceInline(admin.TabularInline):
    model = ClientService
    extra = 0
    fields = ("service", "service_number", "created_at")
    readonly_fields = ("service_number", "created_at")


# ============================================================
# Админка Клиентов
# ============================================================

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "account_number",
        "phone_number",
        "email",
        "is_company",
        "services_count",
    )

    search_fields = (
        "full_name",
        "account_number",
        "phone_number",
        "email",
    )

    list_filter = ("is_company",)

    inlines = [ClientServiceInline]

    def services_count(self, obj):
        return obj.clientservice_set.count()

    services_count.short_description = "Кол-во услуг"


# ============================================================
# Админка Услуг
# ============================================================

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("title", "service_type", "price")
    search_fields = ("title",)
    list_filter = ("service_type",)


# ============================================================
# Админка Услуг Клиента
# ============================================================

@admin.register(ClientService)
class ClientServiceAdmin(admin.ModelAdmin):
    list_display = ("client", "service", "service_number", "created_at")
    search_fields = ("service_number", "client__full_name", "service__title")
    list_filter = ("service__service_type",)
    readonly_fields = ("service_number", "created_at")


# ============================================================
# Админка Инженеров
# ============================================================

@admin.register(Engineer)
class EngineerAdmin(admin.ModelAdmin):
    list_display = ("full_name", "is_active", "active_tickets_count")
    search_fields = ("full_name",)
    list_filter = ("is_active",)
    readonly_fields = ("active_tickets_count",)


# ============================================================
# Админка Заявок
# ============================================================

@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "client",
        "engineer",
        "priority_score",
        "status",
        "created_at",
        "closed_at",
    )

    search_fields = (
        "id",
        "client__full_name",
        "engineer__full_name",
    )

    list_filter = ("status",)

    readonly_fields = ("created_at", "closed_at")
