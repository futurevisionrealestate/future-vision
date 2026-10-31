from django.contrib import admin

from operations.models import DailyTarget, Property, PropertyImage


class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 1


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = (
        "property_code",
        "title",
        "property_type",
        "purpose",
        "city",
        "price",
        "status",
        "created_by",
        "branch",
        "created_at",
    )
    list_filter = ("status", "property_type", "purpose", "city", "branch", "created_at")
    search_fields = ("property_code", "title", "city", "area", "contact_name", "contact_phone")
    readonly_fields = ("property_code", "approved_by", "approved_at", "created_at", "updated_at")
    inlines = (PropertyImageInline,)
    raw_id_fields = ("created_by", "branch", "approved_by")


@admin.register(PropertyImage)
class PropertyImageAdmin(admin.ModelAdmin):
    list_display = ("property", "caption", "is_cover", "uploaded_at")
    list_filter = ("is_cover",)
    search_fields = ("property__property_code", "caption")


@admin.register(DailyTarget)
class DailyTargetAdmin(admin.ModelAdmin):
    list_display = ("user", "date", "target_count", "created_by", "updated_at")
    list_filter = ("date",)
    search_fields = ("user__username", "user__first_name", "user__last_name")
