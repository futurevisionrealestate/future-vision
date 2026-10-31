from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.models import ActivityLog, SiteSetting
from core.scoping import scope_properties, scope_targets
from core.utils import csv_response, date_range_from_request
from operations.forms import (
    DailyTargetForm,
    PropertyFilterForm,
    PropertyForm,
    PropertyImageFormSet,
    PropertyRejectForm,
)
from operations.models import DailyTarget, Property


def _property_queryset(user):
    return scope_properties(
        Property.objects.select_related("created_by", "branch", "approved_by"),
        user,
    )


def _can_moderate(user):
    return user.is_executive or user.is_head_office


def _can_edit(user, obj):
    return (
        user.is_executive
        or user.is_head_office
        or user.is_branch_manager
        or obj.created_by_id == user.pk
    )


@login_required
def property_list(request):
    queryset = _property_queryset(request.user)
    filters = PropertyFilterForm(request.GET or None)
    if filters.is_valid():
        q = filters.cleaned_data.get("q")
        status = filters.cleaned_data.get("status")
        purpose = filters.cleaned_data.get("purpose")
        property_type = filters.cleaned_data.get("property_type")
        branch = filters.cleaned_data.get("branch")
        if q:
            queryset = queryset.filter(
                Q(property_code__icontains=q)
                | Q(title__icontains=q)
                | Q(city__icontains=q)
                | Q(area__icontains=q)
                | Q(contact_name__icontains=q)
                | Q(contact_phone__icontains=q)
            )
        if status:
            queryset = queryset.filter(status=status)
        if purpose:
            queryset = queryset.filter(purpose=purpose)
        if property_type:
            queryset = queryset.filter(property_type=property_type)
        if branch:
            queryset = queryset.filter(branch=branch)

    page_obj = Paginator(queryset, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "operations/property_list.html",
        {"page_obj": page_obj, "filters": filters},
    )


@login_required
def property_export(request):
    queryset = _property_queryset(request.user)
    rows = [
        [
            p.property_code,
            p.title,
            p.get_property_type_display(),
            p.get_purpose_display(),
            p.city,
            p.area,
            p.size_display,
            p.price or "",
            p.get_status_display(),
            p.created_by.display_name,
            p.branch.name if p.branch else "",
            p.created_at.strftime("%Y-%m-%d"),
        ]
        for p in queryset
    ]
    return csv_response(
        "future-vision-properties",
        ["Code", "Title", "Type", "Purpose", "City", "Area", "Size", "Price", "Status", "Created by", "Branch", "Created"],
        rows,
    )


@login_required
def property_detail(request, pk):
    obj = get_object_or_404(_property_queryset(request.user), pk=pk)
    return render(
        request,
        "operations/property_detail.html",
        {
            "property": obj,
            "images": obj.images.all(),
            "deals": obj.deals.select_related("client", "assigned_to"),
            "can_edit": _can_edit(request.user, obj),
            "can_moderate": _can_moderate(request.user),
            "reject_form": PropertyRejectForm(),
        },
    )


@login_required
def property_create(request):
    form = PropertyForm(request.POST or None, request.FILES or None, user=request.user)
    new_property = Property()
    formset = PropertyImageFormSet(
        request.POST or None,
        request.FILES or None,
        instance=new_property,
    )
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            prop = form.save(commit=False)
            prop.created_by = request.user
            prop.branch = prop.branch or request.user.branch
            prop.status = Property.Status.PENDING
            prop.save()
            formset.instance = prop
            formset.save()
        ActivityLog.log(
            request.user,
            "property.create",
            prop,
            f"Registered property {prop.property_code}",
            request,
        )
        messages.success(request, f"Property {prop.property_code} submitted for approval.")
        return redirect("operations:detail", pk=prop.pk)
    return render(
        request,
        "operations/property_form.html",
        {"form": form, "formset": formset, "title": "Register property", "is_create": True},
    )


@login_required
def property_edit(request, pk):
    obj = get_object_or_404(_property_queryset(request.user), pk=pk)
    if not _can_edit(request.user, obj):
        raise PermissionDenied
    form = PropertyForm(request.POST or None, request.FILES or None, instance=obj, user=request.user)
    formset = PropertyImageFormSet(
        request.POST or None,
        request.FILES or None,
        instance=obj,
    )
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            prop = form.save(commit=False)
            if not request.user.is_executive and not request.user.is_head_office:
                prop.status = Property.Status.PENDING
                prop.approved_by = None
                prop.approved_at = None
                prop.rejection_reason = ""
            prop.save()
            formset.instance = prop
            formset.save()
        ActivityLog.log(
            request.user,
            "property.update",
            prop,
            f"Updated property {prop.property_code}",
            request,
        )
        if request.user.is_executive or request.user.is_head_office:
            messages.success(request, "Property updated.")
        else:
            messages.success(request, "Property updated and submitted for approval.")
        return redirect("operations:detail", pk=obj.pk)
    return render(
        request,
        "operations/property_form.html",
        {
            "form": form,
            "formset": formset,
            "property": obj,
            "title": "Edit property",
            "is_create": False,
        },
    )


@login_required
@require_POST
def property_approve(request, pk):
    if not _can_moderate(request.user):
        raise PermissionDenied
    obj = get_object_or_404(Property, pk=pk)
    if obj.status not in {Property.Status.PENDING, Property.Status.REJECTED}:
        messages.error(request, "This property cannot be approved in its current state.")
    else:
        obj.approve(request.user, request)
        messages.success(request, f"{obj.property_code} approved.")
    return redirect("operations:detail", pk=obj.pk)


@login_required
@require_POST
def property_reject(request, pk):
    if not _can_moderate(request.user):
        raise PermissionDenied
    obj = get_object_or_404(Property, pk=pk)
    form = PropertyRejectForm(request.POST)
    if form.is_valid():
        obj.reject(request.user, form.cleaned_data["reason"], request)
        messages.success(request, f"{obj.property_code} rejected.")
    else:
        messages.error(request, "A rejection reason is required.")
    return redirect("operations:detail", pk=obj.pk)


@login_required
def target_list(request):
    queryset = scope_targets(
        DailyTarget.objects.select_related("user", "user__branch"),
        request.user,
    )
    start, end = date_range_from_request(request, default_days=30)
    queryset = queryset.filter(date__range=(start, end))
    user_id = request.GET.get("user", "")
    if user_id and request.user.can_view_all_records:
        queryset = queryset.filter(user_id=user_id)
    page_obj = Paginator(queryset, 30).get_page(request.GET.get("page"))
    return render(
        request,
        "operations/target_list.html",
        {
            "page_obj": page_obj,
            "start": start,
            "end": end,
            "user_id": user_id,
        },
    )


@login_required
def target_create(request):
    site = SiteSetting.load()
    initial = {"target_count": site.default_daily_target, "date": timezone.localdate()}
    if request.user.is_fo or request.user.is_dealer:
        initial["user"] = request.user
    form = DailyTargetForm(request.POST or None, initial=initial, user=request.user)
    if request.method == "POST" and form.is_valid():
        target = form.save(commit=False)
        if request.user.is_fo or request.user.is_dealer:
            target.user = request.user
        elif request.user.is_branch_manager and target.user.branch_id != request.user.branch_id:
            messages.error(request, "You can only set targets for your branch.")
            return redirect("operations:target_create")
        target.created_by = request.user
        existing = DailyTarget.objects.filter(user=target.user, date=target.date).first()
        if existing:
            existing.target_count = target.target_count
            existing.notes = target.notes
            existing.created_by = request.user
            existing.save()
            target = existing
            messages.success(request, "Existing target updated.")
        else:
            target.save()
            messages.success(request, "Target saved.")
        ActivityLog.log(
            request.user,
            "target.set",
            target,
            f"Set target {target.target_count} for {target.user.display_name} on {target.date}",
            request,
        )
        return redirect("operations:target_list")
    return render(
        request,
        "operations/target_form.html",
        {"form": form, "title": "Set daily target"},
    )
