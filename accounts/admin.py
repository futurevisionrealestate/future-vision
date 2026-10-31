from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from accounts.models import Branch, DealerProfile, FOProfile, User


class FOProfileInline(admin.StackedInline):
    model = FOProfile
    extra = 0


class DealerProfileInline(admin.StackedInline):
    model = DealerProfile
    extra = 0


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "username",
        "display_name",
        "email",
        "role",
        "branch",
        "fv_id",
        "is_active",
        "is_staff",
    )
    list_filter = ("role", "branch", "is_active", "is_staff", "can_final_approve")
    search_fields = ("username", "first_name", "last_name", "email", "phone", "fv_id")
    ordering = ("first_name", "last_name", "username")
    inlines = (FOProfileInline, DealerProfileInline)
    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "Future Vision",
            {
                "fields": (
                    "phone",
                    "role",
                    "branch",
                    "fv_id",
                    "can_review_registrations",
                    "can_final_approve",
                    "must_change_password",
                    "approved_at",
                    "last_login_ip",
                )
            },
        ),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (
            "Future Vision",
            {
                "fields": (
                    "email",
                    "phone",
                    "role",
                    "branch",
                    "fv_id",
                    "can_review_registrations",
                    "can_final_approve",
                    "is_active",
                )
            },
        ),
    )


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "city", "manager", "is_active", "active_staff_count")
    list_filter = ("is_active", "city")
    search_fields = ("name", "code", "city", "phone", "email")
    prepopulated_fields = {"code": ("name",)}


@admin.register(FOProfile)
class FOProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "cnic", "city", "experience_years", "date_of_joining")
    search_fields = ("user__username", "user__first_name", "user__last_name", "cnic")


@admin.register(DealerProfile)
class DealerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "business_name", "cnic", "city", "experience_years")
    search_fields = ("user__username", "business_name", "cnic")
