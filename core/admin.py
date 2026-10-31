from django.contrib import admin

from core.models import ActivityLog, IDSequence, Notification, SiteSetting


@admin.register(SiteSetting)
class SiteSettingAdmin(admin.ModelAdmin):
    list_display = ("company_name", "tagline", "approval_mode", "require_review", "updated_at")

    def has_add_permission(self, request):
        return not SiteSetting.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "action", "model_name", "object_repr", "ip_address")
    list_filter = ("action", "model_name", "created_at")
    search_fields = ("description", "object_repr", "actor__username", "ip_address")
    date_hierarchy = "created_at"
    readonly_fields = (
        "actor",
        "action",
        "model_name",
        "object_id",
        "object_repr",
        "description",
        "ip_address",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "title", "is_read")
    list_filter = ("is_read", "created_at")
    search_fields = ("title", "message", "user__username", "user__email")


@admin.register(IDSequence)
class IDSequenceAdmin(admin.ModelAdmin):
    list_display = ("prefix", "last_number")
    readonly_fields = ("prefix", "last_number")
