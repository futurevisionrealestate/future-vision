from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import get_language
from django.views.decorators.http import require_POST

from accounts.forms import (
    AdminPasswordResetForm,
    BranchForm,
    DealerProfileForm,
    FOProfileForm,
    LoginForm,
    ProfileForm,
    RegistrationApplyForm,
    UserCreateForm,
    UserUpdateForm,
)
from accounts.models import Branch, DealerProfile, FOProfile, User
from core.decorators import executive_required, manager_or_executive_required
from core.i18n import translations
from core.models import ActivityLog, Notification, SiteSetting
from core.scoping import scope_users
from core.utils import csv_response


def _safe_next(request, fallback):
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return fallback


def login_view(request):
    if request.user.is_authenticated:
        return redirect("core:dashboard")

    next_url = _safe_next(request, reverse("core:dashboard"))
    form = LoginForm(request, data=request.POST or None)
    if request.method == "POST":
        key = f"login-attempts:{ActivityLog.client_ip(request)}"
        attempts = cache.get(key, 0)
        if attempts >= 8:
            t = translations(get_language())
            messages.error(
                request,
                t.get(
                    "rate_limited", "Too many failed attempts. Please wait 15 minutes."
                ),
            )
            return render(
                request,
                "accounts/login.html",
                {"form": LoginForm(request), "next": next_url},
                status=429,
            )
        if form.is_valid():
            user = form.get_user()
            if not user.is_active:
                t = translations(get_language())
                messages.error(
                    request,
                    t.get(
                        "account_inactive",
                        "This account is not active. Complete approval or contact Head Office.",
                    ),
                )
            else:
                auth_login(request, user)
                cache.delete(key)
                user.last_login_ip = ActivityLog.client_ip(request)
                user.save(update_fields=["last_login_ip"])
                ActivityLog.log(user, "auth.login", user, "User signed in", request)
                messages.success(request, f"Welcome back, {user.display_name}.")
                return redirect(next_url)
        else:
            cache.set(key, attempts + 1, timeout=60 * 15)
            # The form already shows a safe, generic error message.
    return render(request, "accounts/login.html", {"form": form, "next": next_url})


@require_POST
@login_required
def logout_view(request):
    ActivityLog.log(request.user, "auth.logout", request.user, "User signed out", request)
    auth_logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("core:home")


def register_view(request):
    site = SiteSetting.load()
    if not site.public_registration_enabled:
        return render(request, "accounts/registration_closed.html", status=403)

    form = RegistrationApplyForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        registration = form.save()
        ActivityLog.log(
            None,
            "registration.submit",
            registration,
            f"Public application {registration.request_no} submitted",
            request,
        )
        messages.success(
            request,
            f"Application submitted. Your application number is {registration.request_no}.",
        )
        return redirect(
            f"{reverse('registrations:status_check')}?request_no={registration.request_no}"
        )
    return render(request, "accounts/register.html", {"form": form})


@login_required
def profile_view(request):
    common_form = ProfileForm(instance=request.user)
    profile_form = None
    profile_obj = None
    if request.user.is_fo:
        profile_obj, _ = FOProfile.objects.get_or_create(user=request.user)
        profile_form = FOProfileForm(instance=profile_obj)
    elif request.user.is_dealer:
        profile_obj, _ = DealerProfile.objects.get_or_create(user=request.user)
        profile_form = DealerProfileForm(instance=profile_obj)

    if request.method == "POST":
        common_form = ProfileForm(request.POST, instance=request.user)
        if profile_form is not None:
            profile_form = (
                FOProfileForm(request.POST, instance=profile_obj)
                if request.user.is_fo
                else DealerProfileForm(request.POST, instance=profile_obj)
            )
        if common_form.is_valid() and (profile_form is None or profile_form.is_valid()):
            common_form.save()
            if profile_form is not None:
                profile_form.save()
            ActivityLog.log(request.user, "profile.update", request.user, "Profile updated", request)
            messages.success(request, "Profile updated.")
            return redirect("accounts:profile")

    return render(
        request,
        "accounts/profile.html",
        {
            "common_form": common_form,
            "profile_form": profile_form,
        },
    )


@login_required
def change_password_view(request):
    form = PasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        ActivityLog.log(user, "auth.password_change", user, "Password changed", request)
        messages.success(request, "Password changed successfully.")
        return redirect("accounts:profile")
    return render(request, "accounts/password_change.html", {"form": form})


@manager_or_executive_required
def user_list(request):
    users = scope_users(User.objects.select_related("branch"), request.user)
    q = request.GET.get("q", "").strip()
    role = request.GET.get("role", "")
    branch = request.GET.get("branch", "")
    status = request.GET.get("status", "")
    if q:
        users = users.filter(
            Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(username__icontains=q)
            | Q(email__icontains=q)
            | Q(phone__icontains=q)
            | Q(fv_id__icontains=q)
        )
    if role:
        users = users.filter(role=role)
    if branch:
        users = users.filter(branch_id=branch)
    if status == "active":
        users = users.filter(is_active=True)
    elif status == "inactive":
        users = users.filter(is_active=False)

    page_obj = Paginator(users, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "accounts/user_list.html",
        {
            "page_obj": page_obj,
            "q": q,
            "role": role,
            "branch_id": branch,
            "status": status,
            "branches": Branch.objects.filter(is_active=True),
            "roles": User.Role.choices,
        },
    )


@manager_or_executive_required
def user_export(request):
    users = scope_users(User.objects.select_related("branch"), request.user)
    rows = [
        [
            u.fv_id or "",
            u.get_full_name() or u.username,
            u.username,
            u.email,
            u.phone,
            u.get_role_display(),
            u.branch.name if u.branch else "",
            "Active" if u.is_active else "Inactive",
            u.date_joined.strftime("%Y-%m-%d"),
        ]
        for u in users
    ]
    return csv_response(
        "future-vision-users",
        ["FV ID", "Name", "Username", "Email", "Phone", "Role", "Branch", "Status", "Joined"],
        rows,
    )


@manager_or_executive_required
def user_detail(request, pk):
    users = scope_users(User.objects.select_related("branch"), request.user)
    user = get_object_or_404(users, pk=pk)
    return render(request, "accounts/user_detail.html", {"profile_user": user})


@executive_required
def user_create(request):
    form = UserCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        ActivityLog.log(request.user, "user.create", user, f"Created user {user.username}", request)
        Notification.notify(
            user,
            "Account created",
            "Your Future Vision account has been created by an administrator.",
            reverse("accounts:login"),
        )
        messages.success(request, f"User {user.display_name} created.")
        return redirect("accounts:user_detail", pk=user.pk)
    return render(
        request,
        "accounts/user_form.html",
        {"form": form, "title": "Add user", "is_create": True},
    )


@executive_required
def user_edit(request, pk):
    user = get_object_or_404(User, pk=pk)
    form = UserUpdateForm(request.POST or None, instance=user)
    if request.method == "POST" and form.is_valid():
        updated = form.save(commit=False)
        if updated.pk == request.user.pk and not updated.is_active:
            messages.error(request, "You cannot deactivate your own account.")
        else:
            updated.save()
            ActivityLog.log(
                request.user,
                "user.update",
                updated,
                f"Updated user {updated.username}",
                request,
            )
            messages.success(request, "User updated.")
            return redirect("accounts:user_detail", pk=updated.pk)
    return render(
        request,
        "accounts/user_form.html",
        {"form": form, "title": "Edit user", "profile_user": user, "is_create": False},
    )


@executive_required
@require_POST
def user_toggle_active(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user.pk == request.user.pk:
        messages.error(request, "You cannot deactivate your own account.")
        return redirect("accounts:user_detail", pk=user.pk)
    user.is_active = not user.is_active
    user.save(update_fields=["is_active", "updated_at"])
    action = "user.activate" if user.is_active else "user.deactivate"
    ActivityLog.log(request.user, action, user, f"Account {'activated' if user.is_active else 'deactivated'}", request)
    messages.success(
        request,
        f"{user.display_name} has been {'activated' if user.is_active else 'deactivated'}.",
    )
    return redirect("accounts:user_detail", pk=user.pk)


@executive_required
def user_reset_password(request, pk):
    user = get_object_or_404(User, pk=pk)
    form = AdminPasswordResetForm(user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        ActivityLog.log(request.user, "user.password_reset", user, "Password reset by admin", request)
        messages.success(request, f"Password reset for {user.display_name}.")
        return redirect("accounts:user_detail", pk=user.pk)
    return render(
        request,
        "accounts/password_reset_confirm_admin.html",
        {"form": form, "profile_user": user},
    )


@executive_required
def branch_list(request):
    branches = Branch.objects.select_related("manager").all()
    q = request.GET.get("q", "").strip()
    if q:
        branches = branches.filter(
            Q(name__icontains=q) | Q(code__icontains=q) | Q(city__icontains=q)
        )
    page_obj = Paginator(branches, 20).get_page(request.GET.get("page"))
    return render(request, "accounts/branch_list.html", {"page_obj": page_obj, "q": q})


@executive_required
def branch_create(request):
    form = BranchForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        branch = form.save()
        ActivityLog.log(request.user, "branch.create", branch, f"Created branch {branch.code}", request)
        messages.success(request, "Branch created.")
        return redirect("accounts:branch_list")
    return render(
        request,
        "accounts/branch_form.html",
        {"form": form, "title": "Add branch", "is_create": True},
    )


@executive_required
def branch_edit(request, pk):
    branch = get_object_or_404(Branch, pk=pk)
    form = BranchForm(request.POST or None, instance=branch)
    if request.method == "POST" and form.is_valid():
        branch = form.save()
        ActivityLog.log(request.user, "branch.update", branch, f"Updated branch {branch.code}", request)
        messages.success(request, "Branch updated.")
        return redirect("accounts:branch_list")
    return render(
        request,
        "accounts/branch_form.html",
        {"form": form, "title": "Edit branch", "branch": branch, "is_create": False},
    )


def permission_denied_view(request, exception=None):
    return render(request, "errors/403.html", status=403)


def page_not_found_view(request, exception=None):
    return render(request, "errors/404.html", status=404)


def server_error_view(request):
    return render(request, "errors/500.html", status=500)
