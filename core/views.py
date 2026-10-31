import json
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import connection
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import Branch, User
from core.decorators import executive_required, reports_required
from core.forms import SiteSettingForm
from core.models import ActivityLog, Notification, SiteSetting
from core.scoping import (
    scope_clients,
    scope_deals,
    scope_properties,
    scope_registrations,
    scope_targets,
    scope_users,
)
from core.utils import date_range_from_request
from crm.models import Client, Deal
from operations.models import DailyTarget, Property
from registrations.models import RegistrationRequest


def home(request):
    """The domain root is the private entry point, never a public homepage."""
    if request.user.is_authenticated:
        return redirect("core:dashboard")
    return redirect("accounts:login")


def _month_series(queryset, months=6):
    today = timezone.localdate()
    first_month = date(today.year, today.month, 1)
    for _ in range(months - 1):
        first_month = (first_month - timedelta(days=1)).replace(day=1)
    rows = (
        queryset.filter(created_at__date__gte=first_month)
        .values("created_at__year", "created_at__month")
        .annotate(count=Count("id"))
    )
    counts = {(row["created_at__year"], row["created_at__month"]): row["count"] for row in rows}
    result = []
    cursor = first_month
    for _ in range(months):
        result.append(
            {
                "label": cursor.strftime("%b"),
                "year": cursor.year,
                "month": cursor.month,
                "count": counts.get((cursor.year, cursor.month), 0),
            }
        )
        cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
    max_value = max([item["count"] for item in result] or [1]) or 1
    for item in result:
        item["height"] = max(4, round(item["count"] / max_value * 100))
    return result


@login_required
def dashboard(request):
    user = request.user
    site = SiteSetting.load()
    today = timezone.localdate()
    month_start = today.replace(day=1)

    users_qs = scope_users(User.objects.all(), user)
    properties_qs = scope_properties(Property.objects.select_related("created_by", "branch"), user)
    clients_qs = scope_clients(Client.objects.all(), user)
    deals_qs = scope_deals(Deal.objects.all(), user)
    requests_qs = scope_registrations(RegistrationRequest.objects.all(), user)

    pending_requests = requests_qs.filter(
        status__in=[
            RegistrationRequest.Status.PENDING,
            RegistrationRequest.Status.UNDER_REVIEW,
        ]
    )
    approved_users = users_qs.filter(is_active=True).exclude(role=User.Role.DEALER)
    active_clients = clients_qs.filter(status=Client.Status.ACTIVE)
    won_deals = deals_qs.filter(status=Deal.Status.CLOSED_WON)
    commission_total = won_deals.aggregate(total=Sum("commission"))["total"] or Decimal("0")

    stats = []
    if user.is_executive or user.is_head_office:
        stats = [
            {
                "label": "Approved users",
                "value": approved_users.count(),
                "icon": "users",
                "tone": "navy",
                "url": "accounts:user_list",
            },
            {
                "label": "Pending approvals",
                "value": pending_requests.count(),
                "icon": "clipboard",
                "tone": "gold",
                "url": "registrations:list",
            },
            {
                "label": "Properties",
                "value": properties_qs.count(),
                "icon": "building",
                "tone": "success",
                "url": "operations:list",
            },
            {
                "label": "Active clients",
                "value": active_clients.count(),
                "icon": "users",
                "tone": "info",
                "url": "crm:client_list",
            },
        ]
    elif user.is_branch_manager:
        stats = [
            {
                "label": "Branch staff",
                "value": users_qs.filter(is_active=True).count(),
                "icon": "users",
                "tone": "navy",
                "url": "accounts:user_list",
            },
            {
                "label": "Pending approvals",
                "value": pending_requests.count(),
                "icon": "clipboard",
                "tone": "gold",
                "url": "registrations:list",
            },
            {
                "label": "Branch properties",
                "value": properties_qs.count(),
                "icon": "building",
                "tone": "success",
                "url": "operations:list",
            },
            {
                "label": "Branch clients",
                "value": active_clients.count(),
                "icon": "users",
                "tone": "info",
                "url": "crm:client_list",
            },
        ]
    elif user.is_fo:
        target, _ = DailyTarget.objects.get_or_create(
            user=user,
            date=today,
            defaults={
                "target_count": site.default_daily_target,
                "created_by": user,
            },
        )
        stats = [
            {
                "label": "My properties",
                "value": properties_qs.count(),
                "icon": "building",
                "tone": "navy",
                "url": "operations:list",
            },
            {
                "label": "My clients",
                "value": clients_qs.count(),
                "icon": "users",
                "tone": "info",
                "url": "crm:client_list",
            },
            {
                "label": "My deals",
                "value": deals_qs.count(),
                "icon": "handshake",
                "tone": "success",
                "url": "crm:deal_list",
            },
            {
                "label": "Today's target",
                "value": f"{target.achieved_count}/{target.target_count}",
                "icon": "target",
                "tone": "gold",
                "url": "operations:target_list",
            },
        ]
    else:
        stats = [
            {
                "label": "My properties",
                "value": properties_qs.count(),
                "icon": "building",
                "tone": "navy",
                "url": "operations:list",
            },
            {
                "label": "My clients",
                "value": clients_qs.count(),
                "icon": "users",
                "tone": "info",
                "url": "crm:client_list",
            },
            {
                "label": "My deals",
                "value": deals_qs.count(),
                "icon": "handshake",
                "tone": "success",
                "url": "crm:deal_list",
            },
            {
                "label": "Application status",
                "value": requests_qs.first().get_status_display() if requests_qs.exists() else "Approved",
                "icon": "check",
                "tone": "gold",
                "url": "registrations:my_application",
            },
        ]

    target_obj = None
    if user.is_fo:
        target_obj = DailyTarget.objects.filter(user=user, date=today).first()

    target_summary = None
    if user.is_branch_manager or user.is_executive or user.is_head_office:
        target_qs = scope_targets(DailyTarget.objects.filter(date=today), user)
        achieved = properties_qs.filter(created_at__date=today).exclude(
            status=Property.Status.DRAFT
        ).count()
        target_total = target_qs.aggregate(total=Sum("target_count"))["total"] or 0
        target_summary = {
            "target": target_total,
            "achieved": achieved,
            "percent": min(100, round(achieved / target_total * 100)) if target_total else 0,
        }

    status_counts = {
        row["status"]: row["count"]
        for row in properties_qs.values("status").annotate(count=Count("id"))
    }
    total_properties = sum(status_counts.values()) or 1
    property_status = []
    for key, label in Property.Status.choices:
        count = status_counts.get(key, 0)
        property_status.append(
            {
                "key": key,
                "label": label,
                "count": count,
                "percent": round(count / total_properties * 100),
            }
        )

    top_fos = []
    if not (user.is_fo or user.is_dealer):
        top_qs = User.objects.filter(role=User.Role.FO, is_active=True)
        if user.is_branch_manager:
            top_qs = top_qs.filter(branch=user.branch)
        top_fos = (
            top_qs.annotate(
                month_properties=Count(
                    "properties",
                    filter=Q(properties__created_at__date__gte=month_start),
                )
            )
            .order_by("-month_properties", "first_name")[:5]
        )

    recent_requests = (
        pending_requests.select_related("user", "branch").order_by("-created_at")[:5]
        if (user.can_review_registrations or user.can_final_approve or user.is_branch_manager)
        else []
    )

    if user.is_executive:
        activity = ActivityLog.objects.select_related("actor")[:8]
    elif user.is_branch_manager and user.branch:
        activity = ActivityLog.objects.select_related("actor").filter(
            Q(actor__branch=user.branch) | Q(actor=user)
        )[:8]
    else:
        activity = ActivityLog.objects.select_related("actor").filter(actor=user)[:8]

    context = {
        "stats": stats,
        "properties_qs": properties_qs,
        "pending_requests": pending_requests if user.can_view_all_records else None,
        "recent_properties": properties_qs.order_by("-created_at")[:5],
        "recent_requests": recent_requests,
        "recent_activity": activity,
        "monthly_properties": _month_series(properties_qs),
        "property_status": property_status,
        "top_fos": top_fos,
        "commission_total": commission_total,
        "won_deals_count": won_deals.count(),
        "total_properties": properties_qs.count(),
        "target_obj": target_obj,
        "target_summary": target_summary,
        "site": site,
        "today": today,
    }
    return render(request, "core/dashboard.html", context)


@login_required
def notifications(request):
    qs = request.user.notifications.all()
    page_obj = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(request, "core/notifications.html", {"page_obj": page_obj})


@require_POST
@login_required
def mark_all_notifications_read(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    messages.success(request, "All notifications marked as read.")
    return redirect("core:notifications")


@login_required
def open_notification(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.is_read = True
    notification.save(update_fields=["is_read"])
    return redirect(notification.get_absolute_url())


@reports_required
def reports(request):
    start, end = date_range_from_request(request)
    branch_id = request.GET.get("branch", "")
    user = request.user

    properties_qs = scope_properties(Property.objects.select_related("branch", "created_by"), user)
    clients_qs = scope_clients(Client.objects.all(), user)
    deals_qs = scope_deals(Deal.objects.all(), user)
    requests_qs = scope_registrations(RegistrationRequest.objects.all(), user)
    targets_qs = scope_targets(DailyTarget.objects.select_related("user"), user)

    if branch_id:
        properties_qs = properties_qs.filter(branch_id=branch_id)
        clients_qs = clients_qs.filter(branch_id=branch_id)
        deals_qs = deals_qs.filter(branch_id=branch_id)
        requests_qs = requests_qs.filter(branch_id=branch_id)
        targets_qs = targets_qs.filter(user__branch_id=branch_id)

    properties_in_range = properties_qs.filter(created_at__date__range=(start, end))
    deals_in_range = deals_qs.filter(deal_date__range=(start, end))
    requests_in_range = requests_qs.filter(created_at__date__range=(start, end))
    targets_in_range = targets_qs.filter(date__range=(start, end))

    won_deals = deals_in_range.filter(status=Deal.Status.CLOSED_WON)
    summary = {
        "properties": properties_in_range.count(),
        "property_value": properties_in_range.aggregate(total=Sum("price"))["total"] or 0,
        "requests": requests_in_range.count(),
        "approved_requests": requests_in_range.filter(
            status=RegistrationRequest.Status.APPROVED
        ).count(),
        "deals": deals_in_range.count(),
        "won_deals": won_deals.count(),
        "deal_value": won_deals.aggregate(total=Sum("amount"))["total"] or 0,
        "commission": won_deals.aggregate(total=Sum("commission"))["total"] or 0,
        "targets": targets_in_range.aggregate(total=Sum("target_count"))["total"] or 0,
    }

    monthly = _month_series(properties_qs)

    branch_rows = []
    branches = Branch.objects.all() if user.is_executive or user.is_head_office else Branch.objects.filter(pk=user.branch_id)
    for branch in branches:
        branch_props = properties_in_range.filter(branch=branch)
        branch_deals = deals_in_range.filter(branch=branch)
        branch_rows.append(
            {
                "branch": branch,
                "properties": branch_props.count(),
                "value": branch_props.aggregate(total=Sum("price"))["total"] or 0,
                "deals": branch_deals.count(),
                "commission": branch_deals.filter(status=Deal.Status.CLOSED_WON).aggregate(
                    total=Sum("commission")
                )["total"]
                or 0,
            }
        )

    top_fos = []
    if user.is_executive or user.is_head_office or user.is_branch_manager:
        top_qs = User.objects.filter(role=User.Role.FO, is_active=True)
        if user.is_branch_manager:
            top_qs = top_qs.filter(branch=user.branch)
        top_fos = top_qs.annotate(
            period_properties=Count(
                "properties",
                filter=Q(
                    properties__created_at__date__range=(start, end),
                    properties__status__in=[
                        Property.Status.APPROVED,
                        Property.Status.SOLD,
                        Property.Status.RENTED,
                    ],
                ),
            )
        ).order_by("-period_properties", "first_name")[:10]

    return render(
        request,
        "core/reports.html",
        {
            "start": start,
            "end": end,
            "branch_id": branch_id,
            "branches": Branch.objects.filter(is_active=True),
            "summary": summary,
            "monthly": monthly,
            "branch_rows": branch_rows,
            "top_fos": top_fos,
            "recent_properties": properties_in_range.select_related("branch", "created_by")[:10],
            "recent_deals": deals_in_range.select_related("property", "client", "assigned_to")[:10],
        },
    )


@executive_required
def audit_logs(request):
    qs = ActivityLog.objects.select_related("actor")
    q = request.GET.get("q", "").strip()
    action = request.GET.get("action", "")
    if q:
        qs = qs.filter(
            Q(description__icontains=q)
            | Q(object_repr__icontains=q)
            | Q(actor__username__icontains=q)
            | Q(actor__first_name__icontains=q)
        )
    if action:
        qs = qs.filter(action=action)
    actions = (
        ActivityLog.objects.values_list("action", flat=True).distinct().order_by("action")
    )
    page_obj = Paginator(qs, 30).get_page(request.GET.get("page"))
    return render(
        request,
        "core/audit_logs.html",
        {"page_obj": page_obj, "q": q, "action": action, "actions": actions},
    )


@executive_required
def settings_view(request):
    site = SiteSetting.load()
    form = SiteSettingForm(request.POST or None, instance=site)
    if request.method == "POST" and form.is_valid():
        form.save()
        ActivityLog.log(request.user, "settings.update", site, "Updated system settings", request)
        messages.success(request, "Settings saved.")
        return redirect("core:settings")
    return render(request, "core/settings.html", {"form": form, "site": site})


@login_required
def search(request):
    q = request.GET.get("q", "").strip()
    properties = clients = users = requests = deals = []
    if q:
        properties = scope_properties(Property.objects.filter(
            Q(property_code__icontains=q)
            | Q(title__icontains=q)
            | Q(city__icontains=q)
            | Q(area__icontains=q)
            | Q(contact_name__icontains=q)
            | Q(contact_phone__icontains=q)
        ), request.user)[:10]
        clients = scope_clients(Client.objects.filter(
            Q(client_code__icontains=q)
            | Q(name__icontains=q)
            | Q(phone__icontains=q)
            | Q(city__icontains=q)
        ), request.user)[:10]
        deals = scope_deals(Deal.objects.filter(
            Q(deal_code__icontains=q)
            | Q(property__title__icontains=q)
            | Q(client__name__icontains=q)
        ), request.user)[:10]
        if request.user.can_manage_users or request.user.is_branch_manager:
            users = scope_users(
                User.objects.filter(
                    Q(username__icontains=q)
                    | Q(first_name__icontains=q)
                    | Q(last_name__icontains=q)
                    | Q(fv_id__icontains=q)
                    | Q(phone__icontains=q)
                ),
                request.user,
            )[:10]
        if request.user.can_view_all_records or request.user.is_branch_manager:
            requests = scope_registrations(RegistrationRequest.objects.filter(
                Q(request_no__icontains=q)
                | Q(full_name__icontains=q)
                | Q(phone__icontains=q)
                | Q(cnic__icontains=q)
            ), request.user)[:10]
    return render(
        request,
        "core/search.html",
        {
            "q": q,
            "properties": properties,
            "clients": clients,
            "deals": deals,
            "users": users,
            "requests": requests,
        },
    )


def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        status = "ok"
        code = 200
    except Exception:
        status = "error"
        code = 500
    return JsonResponse({"status": status, "version": settings.APP_VERSION}, status=code)
