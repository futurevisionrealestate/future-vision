from django.contrib import admin

from crm.models import Client, Deal


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = (
        "client_code",
        "name",
        "phone",
        "client_type",
        "city",
        "status",
        "assigned_to",
        "branch",
        "created_at",
    )
    list_filter = ("client_type", "status", "source", "city", "branch", "created_at")
    search_fields = ("client_code", "name", "phone", "email", "city", "area")
    readonly_fields = ("client_code", "created_at", "updated_at")
    raw_id_fields = ("assigned_to", "branch", "created_by")


@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = (
        "deal_code",
        "property",
        "client",
        "deal_type",
        "amount",
        "commission",
        "status",
        "deal_date",
        "assigned_to",
    )
    list_filter = ("status", "deal_type", "deal_date", "branch")
    search_fields = ("deal_code", "property__property_code", "client__name")
    readonly_fields = ("deal_code", "closed_at", "created_at", "updated_at")
    raw_id_fields = ("property", "client", "assigned_to", "branch", "created_by")
