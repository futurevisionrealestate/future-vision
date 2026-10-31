from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from core.models import ActivityLog, SiteSetting
from core.scoping import scope_registrations
from core.utils import csv_response
from registrations.forms import (
    RegistrationFilterForm,
    RejectForm,
    ReviewForm,
    StatusCheckForm,
)
from registrations.models import RegistrationRequest


def _can_view(user, obj):
    if user.can_view_all_records:
        return True
    if user.is_branch_manager:
        return bool(user.branch_id and obj.branch_id == user.branch_id)
    return obj.user_id == user.pk


def _can_review(user):
    return user.is_executive or user.can_review_registrations or user.can_final_approve


def _can_approve(user):
    site = SiteSetting.load()
    if site.approval_mode == SiteSetting.ApprovalMode.CEO_ONLY:
        return user.is_executive
    return user.is_executive or user.can_final_approve


@login_required
def registration_list(request):
    if request.user.is_fo or request.user.is_dealer:
        return redirect("registrations:my_application")
    if not (request.user.can_review_registrations or request.user.can_final_approve or request.user.is_branch_manager or request.user.is_executive):
        raise PermissionDenied

    queryset = scope_registrations(
        RegistrationRequest.objects.select_related("user", "branch", "reviewed_by", "approved_by"),
        request.user,
    )
    filters = RegistrationFilterForm(request.GET or None)
    if filters.is_valid():
        q = filters.cleaned_data.get("q")
        status = filters.cleaned_data.get("status")
        applicant_type = filters.cleaned_data.get("applicant_type")
        branch = filters.cleaned_data.get("branch")
        if q:
            queryset = queryset.filter(
                Q(request_no__icontains=q)
                | Q(full_name__icontains=q)
                | Q(phone__icontains=q)
                | Q(email__icontains=q)
                | Q(cnic__icontains=q)
            )
        if status:
            queryset = queryset.filter(status=status)
        if applicant_type:
            queryset = queryset.filter(applicant_type=applicant_type)
        if branch:
            queryset = queryset.filter(branch=branch)

    page_obj = Paginator(queryset, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "registrations/list.html",
        {"page_obj": page_obj, "filters": filters},
    )


@login_required
def registration_export(request):
    if not (request.user.is_executive or request.user.is_head_office or request.user.is_branch_manager):
        raise PermissionDenied
    queryset = scope_registrations(RegistrationRequest.objects.all(), request.user)
    rows = [
        [
            r.request_no,
            r.full_name,
            r.get_applicant_type_display(),
            r.phone,
            r.email,
            r.branch.name if r.branch else "",
            r.get_status_display(),
            r.fv_id_issued,
            r.created_at.strftime("%Y-%m-%d %H:%M"),
            r.approved_by.display_name if r.approved_by else "",
        ]
        for r in queryset
    ]
    return csv_response(
        "future-vision-registrations",
        ["Request", "Name", "Type", "Phone", "Email", "Branch", "Status", "FV ID", "Submitted", "Approved by"],
        rows,
    )


@login_required
def registration_detail(request, pk):
    obj = get_object_or_404(
        RegistrationRequest.objects.select_related(
            "user", "branch", "reviewed_by", "approved_by", "rejected_by"
        ),
        pk=pk,
    )
    if not _can_view(request.user, obj):
        raise PermissionDenied

    return render(
        request,
        "registrations/detail.html",
        {
            "registration": obj,
            "review_form": ReviewForm(),
            "reject_form": RejectForm(),
            "can_review": _can_review(request.user) and obj.status == RegistrationRequest.Status.PENDING,
            "can_approve": _can_approve(request.user) and obj.status in {
                RegistrationRequest.Status.PENDING,
                RegistrationRequest.Status.UNDER_REVIEW,
            },
            "can_reject": _can_review(request.user) and obj.status in {
                RegistrationRequest.Status.PENDING,
                RegistrationRequest.Status.UNDER_REVIEW,
            },
            "approval_logs": obj.approval_logs.select_related("actor"),
        },
    )


@login_required
def my_application(request):
    try:
        obj = request.user.registration_request
    except RegistrationRequest.DoesNotExist:
        if request.user.is_fo or request.user.is_dealer:
            return render(request, "registrations/no_application.html")
        return redirect("core:dashboard")
    return render(request, "registrations/my_application.html", {"registration": obj})


def status_check(request):
    result = None
    error = None
    initial = {"request_no": request.GET.get("request_no", "")}
    form = StatusCheckForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        request_no = form.cleaned_data["request_no"].strip()
        phone_or_cnic = form.cleaned_data["phone_or_cnic"].strip()
        result = RegistrationRequest.objects.filter(request_no__iexact=request_no).filter(
            Q(phone__iexact=phone_or_cnic) | Q(cnic__iexact=phone_or_cnic)
        ).first()
        if result is None:
            error = "No application matched those details. Check the number and try again."
    return render(
        request,
        "registrations/status_check.html",
        {"form": form, "result": result, "error": error},
    )


@require_POST
@login_required
def review_registration(request, pk):
    obj = get_object_or_404(RegistrationRequest, pk=pk)
    if not _can_view(request.user, obj) or not _can_review(request.user):
        raise PermissionDenied
    form = ReviewForm(request.POST)
    if form.is_valid():
        try:
            obj.start_review(request.user, form.cleaned_data["notes"], request)
            messages.success(request, f"{obj.request_no} is now under review.")
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
    else:
        messages.error(request, "Could not start review.")
    return redirect("registrations:detail", pk=obj.pk)


@require_POST
@login_required
def approve_registration(request, pk):
    obj = get_object_or_404(RegistrationRequest, pk=pk)
    if not _can_view(request.user, obj) or not _can_approve(request.user):
        raise PermissionDenied
    site = SiteSetting.load()
    if site.require_review and obj.status == RegistrationRequest.Status.PENDING:
        messages.error(request, "This application must be reviewed before final approval.")
        return redirect("registrations:detail", pk=obj.pk)
    try:
        obj.approve(request.user, request.POST.get("notes", ""), request)
        messages.success(
            request,
            f"Application approved. ID issued: {obj.fv_id_issued}.",
        )
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    return redirect("registrations:detail", pk=obj.pk)


@require_POST
@login_required
def reject_registration(request, pk):
    obj = get_object_or_404(RegistrationRequest, pk=pk)
    if not _can_view(request.user, obj) or not _can_review(request.user):
        raise PermissionDenied
    form = RejectForm(request.POST)
    if form.is_valid():
        try:
            obj.reject(request.user, form.cleaned_data["reason"], request)
            messages.success(request, f"{obj.request_no} was rejected.")
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
    else:
        messages.error(request, "A rejection reason is required.")
    return redirect("registrations:detail", pk=obj.pk)
