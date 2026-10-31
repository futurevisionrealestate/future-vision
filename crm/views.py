from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.models import ActivityLog
from core.scoping import scope_clients, scope_deals
from core.utils import csv_response
from crm.forms import ClientFilterForm, ClientForm, DealFilterForm, DealForm
from crm.models import Client, Deal
from operations.models import Property


def _client_queryset(user):
    return scope_clients(
        Client.objects.select_related("assigned_to", "branch", "created_by"),
        user,
    )


def _deal_queryset(user):
    return scope_deals(
        Deal.objects.select_related("property", "client", "assigned_to", "branch", "created_by"),
        user,
    )


def _can_edit_client(user, obj):
    return (
        user.is_executive
        or user.is_head_office
        or user.is_branch_manager
        or obj.created_by_id == user.pk
        or obj.assigned_to_id == user.pk
    )


def _can_edit_deal(user, obj):
    return (
        user.is_executive
        or user.is_head_office
        or user.is_branch_manager
        or obj.created_by_id == user.pk
        or obj.assigned_to_id == user.pk
    )


@login_required
def client_list(request):
    queryset = _client_queryset(request.user)
    filters = ClientFilterForm(request.GET or None)
    if filters.is_valid():
        q = filters.cleaned_data.get("q")
        client_type = filters.cleaned_data.get("client_type")
        status = filters.cleaned_data.get("status")
        branch = filters.cleaned_data.get("branch")
        if q:
            queryset = queryset.filter(
                Q(client_code__icontains=q)
                | Q(name__icontains=q)
                | Q(phone__icontains=q)
                | Q(email__icontains=q)
                | Q(city__icontains=q)
                | Q(area__icontains=q)
            )
        if client_type:
            queryset = queryset.filter(client_type=client_type)
        if status:
            queryset = queryset.filter(status=status)
        if branch:
            queryset = queryset.filter(branch=branch)
    page_obj = Paginator(queryset, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "crm/client_list.html",
        {"page_obj": page_obj, "filters": filters},
    )


@login_required
def client_export(request):
    rows = [
        [
            c.client_code,
            c.name,
            c.phone,
            c.email,
            c.get_client_type_display(),
            c.city,
            c.area,
            c.budget_display,
            c.get_status_display(),
            c.assigned_to.display_name if c.assigned_to else "",
            c.branch.name if c.branch else "",
            c.created_at.strftime("%Y-%m-%d"),
        ]
        for c in _client_queryset(request.user)
    ]
    return csv_response(
        "future-vision-clients",
        ["Code", "Name", "Phone", "Email", "Type", "City", "Area", "Budget", "Status", "Assigned to", "Branch", "Created"],
        rows,
    )


@login_required
def client_detail(request, pk):
    obj = get_object_or_404(_client_queryset(request.user), pk=pk)
    return render(
        request,
        "crm/client_detail.html",
        {
            "client": obj,
            "deals": obj.deals.select_related("property", "assigned_to"),
            "can_edit": _can_edit_client(request.user, obj),
        },
    )


@login_required
def client_create(request):
    form = ClientForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        client = form.save(commit=False)
        client.created_by = request.user
        client.branch = client.branch or request.user.branch
        if not client.assigned_to_id and (request.user.is_fo or request.user.is_dealer):
            client.assigned_to = request.user
        client.save()
        ActivityLog.log(
            request.user,
            "client.create",
            client,
            f"Created client {client.client_code}",
            request,
        )
        messages.success(request, f"Client {client.client_code} created.")
        return redirect("crm:client_detail", pk=client.pk)
    return render(
        request,
        "crm/client_form.html",
        {"form": form, "title": "Add client", "is_create": True},
    )


@login_required
def client_edit(request, pk):
    obj = get_object_or_404(_client_queryset(request.user), pk=pk)
    if not _can_edit_client(request.user, obj):
        raise PermissionDenied
    form = ClientForm(request.POST or None, instance=obj, user=request.user)
    if request.method == "POST" and form.is_valid():
        client = form.save(commit=False)
        if not request.user.can_view_all_records:
            client.branch = request.user.branch
        client.save()
        ActivityLog.log(
            request.user,
            "client.update",
            client,
            f"Updated client {client.client_code}",
            request,
        )
        messages.success(request, "Client updated.")
        return redirect("crm:client_detail", pk=client.pk)
    return render(
        request,
        "crm/client_form.html",
        {"form": form, "client": obj, "title": "Edit client", "is_create": False},
    )


@login_required
def deal_list(request):
    queryset = _deal_queryset(request.user)
    filters = DealFilterForm(request.GET or None)
    if filters.is_valid():
        q = filters.cleaned_data.get("q")
        status = filters.cleaned_data.get("status")
        deal_type = filters.cleaned_data.get("deal_type")
        branch = filters.cleaned_data.get("branch")
        if q:
            queryset = queryset.filter(
                Q(deal_code__icontains=q)
                | Q(property__title__icontains=q)
                | Q(property__property_code__icontains=q)
                | Q(client__name__icontains=q)
                | Q(client__client_code__icontains=q)
            )
        if status:
            queryset = queryset.filter(status=status)
        if deal_type:
            queryset = queryset.filter(deal_type=deal_type)
        if branch:
            queryset = queryset.filter(branch=branch)
    page_obj = Paginator(queryset, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "crm/deal_list.html",
        {"page_obj": page_obj, "filters": filters},
    )


@login_required
def deal_export(request):
    rows = [
        [
            d.deal_code,
            d.property.property_code,
            d.property.title,
            d.client.name,
            d.get_deal_type_display(),
            d.amount,
            d.commission,
            d.get_status_display(),
            d.deal_date.strftime("%Y-%m-%d"),
            d.assigned_to.display_name if d.assigned_to else "",
            d.branch.name if d.branch else "",
        ]
        for d in _deal_queryset(request.user)
    ]
    return csv_response(
        "future-vision-deals",
        ["Deal", "Property", "Title", "Client", "Type", "Amount", "Commission", "Status", "Date", "Assigned to", "Branch"],
        rows,
    )


@login_required
def deal_detail(request, pk):
    obj = get_object_or_404(_deal_queryset(request.user), pk=pk)
    return render(
        request,
        "crm/deal_detail.html",
        {"deal": obj, "can_edit": _can_edit_deal(request.user, obj)},
    )


@login_required
def deal_create(request):
    form = DealForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        deal = form.save(commit=False)
        deal.created_by = request.user
        deal.branch = deal.branch or request.user.branch
        if not deal.assigned_to_id and (request.user.is_fo or request.user.is_dealer):
            deal.assigned_to = request.user
        deal.save()
        _sync_deal_effects(deal)
        ActivityLog.log(
            request.user,
            "deal.create",
            deal,
            f"Created deal {deal.deal_code}",
            request,
        )
        messages.success(request, f"Deal {deal.deal_code} created.")
        return redirect("crm:deal_detail", pk=deal.pk)
    return render(
        request,
        "crm/deal_form.html",
        {"form": form, "title": "Add deal", "is_create": True},
    )


@login_required
def deal_edit(request, pk):
    obj = get_object_or_404(_deal_queryset(request.user), pk=pk)
    if not _can_edit_deal(request.user, obj):
        raise PermissionDenied
    form = DealForm(request.POST or None, instance=obj, user=request.user)
    if request.method == "POST" and form.is_valid():
        deal = form.save(commit=False)
        if not request.user.can_view_all_records:
            deal.branch = request.user.branch
        deal.save()
        _sync_deal_effects(deal)
        ActivityLog.log(
            request.user,
            "deal.update",
            deal,
            f"Updated deal {deal.deal_code}",
            request,
        )
        messages.success(request, "Deal updated.")
        return redirect("crm:deal_detail", pk=deal.pk)
    return render(
        request,
        "crm/deal_form.html",
        {"form": form, "deal": obj, "title": "Edit deal", "is_create": False},
    )


def _sync_deal_effects(deal):
    if deal.status == Deal.Status.CLOSED_WON:
        if not deal.closed_at:
            deal.closed_at = timezone.now()
            deal.save(update_fields=["closed_at", "updated_at"])
        if deal.deal_type == Deal.Type.SALE:
            deal.property.status = Property.Status.SOLD
        else:
            deal.property.status = Property.Status.RENTED
        deal.property.save(update_fields=["status", "updated_at"])
        deal.client.status = Client.Status.CONVERTED
        deal.client.save(update_fields=["status", "updated_at"])
