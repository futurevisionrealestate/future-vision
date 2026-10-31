from django.contrib import admin

from registrations.models import ApprovalLog, RegistrationRequest


class ApprovalLogInline(admin.TabularInline):
    model = ApprovalLog
    extra = 0
    readonly_fields = ("action", "actor", "notes", "ip_address", "created_at")
    can_delete = False


@admin.register(RegistrationRequest)
class RegistrationRequestAdmin(admin.ModelAdmin):
    list_display = (
        "request_no",
        "full_name",
        "applicant_type",
        "phone",
        "branch",
        "status",
        "fv_id_issued",
        "created_at",
    )
    list_filter = ("status", "applicant_type", "branch", "created_at")
    search_fields = ("request_no", "full_name", "phone", "email", "cnic", "fv_id_issued")
    readonly_fields = (
        "request_no",
        "user",
        "source",
        "status",
        "reviewed_by",
        "reviewed_at",
        "review_notes",
        "approved_by",
        "approved_at",
        "rejected_by",
        "rejected_at",
        "rejection_reason",
        "fv_id_issued",
        "created_at",
        "updated_at",
    )
    inlines = (ApprovalLogInline,)


@admin.register(ApprovalLog)
class ApprovalLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "registration", "action", "actor")
    list_filter = ("action", "created_at")
    search_fields = ("registration__request_no", "actor__username", "notes")
    readonly_fields = ("registration", "action", "actor", "notes", "ip_address", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
