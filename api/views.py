from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import generics, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from accounts.models import Branch, User
from api.serializers import (
    BranchSerializer,
    ClientSerializer,
    DailyTargetSerializer,
    DealSerializer,
    NotificationSerializer,
    PropertySerializer,
    RegistrationRequestSerializer,
    UserSerializer,
)
from core.models import Notification, SiteSetting
from core.scoping import (
    scope_clients,
    scope_deals,
    scope_properties,
    scope_registrations,
    scope_targets,
)
from crm.models import Client, Deal
from crm.views import _sync_deal_effects
from operations.models import DailyTarget, Property
from registrations.models import RegistrationRequest


class IsExecutive(permissions.BasePermission):
    message = "Executive access is required."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_executive)


class MeView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class BranchViewSet(viewsets.ModelViewSet):
    queryset = Branch.objects.select_related("manager").all()
    serializer_class = BranchSerializer
    permission_classes = [IsExecutive]
    search_fields = ["name", "code", "city"]
    ordering_fields = ["name", "code", "city", "created_at"]


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.select_related("branch").all()
    serializer_class = UserSerializer
    permission_classes = [IsExecutive]
    search_fields = ["username", "first_name", "last_name", "email", "fv_id", "phone"]
    ordering_fields = ["username", "first_name", "date_joined", "role"]


class RegistrationRequestViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = RegistrationRequestSerializer
    search_fields = ["request_no", "full_name", "phone", "email", "cnic"]
    ordering_fields = ["created_at", "status", "applicant_type"]

    def get_queryset(self):
        if not getattr(self.request.user, "is_authenticated", False):
            return RegistrationRequest.objects.none()
        return scope_registrations(
            RegistrationRequest.objects.select_related(
                "user", "branch", "reviewed_by", "approved_by"
            ),
            self.request.user,
        )

    def _get_request(self):
        obj = self.get_object()
        if not (
            self.request.user.can_view_all_records
            or (
                self.request.user.is_branch_manager
                and obj.branch_id
                and obj.branch_id == self.request.user.branch_id
            )
            or obj.user_id == self.request.user.pk
        ):
            raise PermissionDenied("You cannot access this application.")
        return obj

    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        obj = self._get_request()
        if not (
            request.user.is_executive
            or request.user.can_review_registrations
            or request.user.can_final_approve
        ):
            raise PermissionDenied("Review permission is required.")
        try:
            obj.start_review(request.user, request.data.get("notes", ""), request)
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages)
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        obj = self._get_request()
        site = SiteSetting.load()
        if site.approval_mode == SiteSetting.ApprovalMode.CEO_ONLY:
            allowed = request.user.is_executive
        else:
            allowed = request.user.is_executive or request.user.can_final_approve
        if not allowed:
            raise PermissionDenied("Final approval permission is required.")
        if site.require_review and obj.status == RegistrationRequest.Status.PENDING:
            raise ValidationError("This application must be reviewed before approval.")
        try:
            obj.approve(request.user, request.data.get("notes", ""), request)
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages)
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        obj = self._get_request()
        if not (
            request.user.is_executive
            or request.user.can_review_registrations
            or request.user.can_final_approve
        ):
            raise PermissionDenied("Review permission is required.")
        reason = (request.data.get("reason") or "").strip()
        if len(reason) < 5:
            raise ValidationError("A rejection reason is required.")
        try:
            obj.reject(request.user, reason, request)
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages)
        return Response(self.get_serializer(obj).data)


class PropertyViewSet(viewsets.ModelViewSet):
    serializer_class = PropertySerializer
    search_fields = ["property_code", "title", "city", "area", "contact_name", "contact_phone"]
    ordering_fields = ["created_at", "price", "status", "city"]

    def get_queryset(self):
        if not getattr(self.request.user, "is_authenticated", False):
            return Property.objects.none()
        return scope_properties(
            Property.objects.select_related("created_by", "branch", "approved_by").prefetch_related(
                "images"
            ),
            self.request.user,
        )

    def perform_create(self, serializer):
        branch = serializer.validated_data.get("branch") or self.request.user.branch
        if not self.request.user.can_view_all_records:
            branch = self.request.user.branch
        serializer.save(
            created_by=self.request.user,
            branch=branch,
            status=Property.Status.PENDING,
        )

    def perform_update(self, serializer):
        prop = self.get_object()
        if not (
            self.request.user.is_executive
            or self.request.user.is_head_office
            or self.request.user.is_branch_manager
            or prop.created_by_id == self.request.user.pk
        ):
            raise PermissionDenied("You cannot edit this property.")
        branch = serializer.validated_data.get("branch") or prop.branch
        if not self.request.user.can_view_all_records:
            branch = self.request.user.branch
        if not (self.request.user.is_executive or self.request.user.is_head_office):
            serializer.save(
                branch=branch,
                status=Property.Status.PENDING,
                approved_by=None,
                approved_at=None,
                rejection_reason="",
            )
        else:
            serializer.save(branch=branch)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        obj = self.get_object()
        if not (request.user.is_executive or request.user.is_head_office):
            raise PermissionDenied("Property approval permission is required.")
        obj.approve(request.user, request)
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        obj = self.get_object()
        if not (request.user.is_executive or request.user.is_head_office):
            raise PermissionDenied("Property approval permission is required.")
        reason = (request.data.get("reason") or "").strip()
        if len(reason) < 5:
            raise ValidationError("A rejection reason is required.")
        obj.reject(request.user, reason, request)
        return Response(self.get_serializer(obj).data)


class ClientViewSet(viewsets.ModelViewSet):
    serializer_class = ClientSerializer
    search_fields = ["client_code", "name", "phone", "email", "city", "area"]
    ordering_fields = ["created_at", "name", "status", "client_type"]

    def get_queryset(self):
        if not getattr(self.request.user, "is_authenticated", False):
            return Client.objects.none()
        return scope_clients(
            Client.objects.select_related("assigned_to", "branch", "created_by"),
            self.request.user,
        )

    def perform_create(self, serializer):
        branch = serializer.validated_data.get("branch") or self.request.user.branch
        if not self.request.user.can_view_all_records:
            branch = self.request.user.branch
        client = serializer.save(
            created_by=self.request.user,
            branch=branch,
        )
        if not client.assigned_to_id and (self.request.user.is_fo or self.request.user.is_dealer):
            client.assigned_to = self.request.user
            client.save(update_fields=["assigned_to", "updated_at"])

    def perform_update(self, serializer):
        client = self.get_object()
        if not (
            self.request.user.is_executive
            or self.request.user.is_head_office
            or self.request.user.is_branch_manager
            or client.created_by_id == self.request.user.pk
            or client.assigned_to_id == self.request.user.pk
        ):
            raise PermissionDenied("You cannot edit this client.")
        branch = client.branch
        if not self.request.user.can_view_all_records:
            branch = self.request.user.branch
        serializer.save(branch=branch)


class DealViewSet(viewsets.ModelViewSet):
    serializer_class = DealSerializer
    search_fields = ["deal_code", "property__title", "property__property_code", "client__name"]
    ordering_fields = ["deal_date", "created_at", "amount", "commission", "status"]

    def get_queryset(self):
        if not getattr(self.request.user, "is_authenticated", False):
            return Deal.objects.none()
        return scope_deals(
            Deal.objects.select_related("property", "client", "assigned_to", "branch", "created_by"),
            self.request.user,
        )

    def perform_create(self, serializer):
        branch = serializer.validated_data.get("branch") or self.request.user.branch
        if not self.request.user.can_view_all_records:
            branch = self.request.user.branch
        deal = serializer.save(
            created_by=self.request.user,
            branch=branch,
        )
        if not deal.assigned_to_id and (self.request.user.is_fo or self.request.user.is_dealer):
            deal.assigned_to = self.request.user
            deal.save(update_fields=["assigned_to", "updated_at"])
        _sync_deal_effects(deal)

    def perform_update(self, serializer):
        deal = self.get_object()
        if not (
            self.request.user.is_executive
            or self.request.user.is_head_office
            or self.request.user.is_branch_manager
            or deal.created_by_id == self.request.user.pk
            or deal.assigned_to_id == self.request.user.pk
        ):
            raise PermissionDenied("You cannot edit this deal.")
        branch = deal.branch
        if not self.request.user.can_view_all_records:
            branch = self.request.user.branch
        deal = serializer.save(branch=branch)
        _sync_deal_effects(deal)


class DailyTargetViewSet(viewsets.ModelViewSet):
    serializer_class = DailyTargetSerializer
    ordering_fields = ["date", "target_count", "created_at"]

    def get_queryset(self):
        if not getattr(self.request.user, "is_authenticated", False):
            return DailyTarget.objects.none()
        return scope_targets(
            DailyTarget.objects.select_related("user", "created_by"),
            self.request.user,
        )

    def perform_create(self, serializer):
        target_user = serializer.validated_data.get("user") or self.request.user
        if self.request.user.is_branch_manager:
            if target_user.branch_id != self.request.user.branch_id:
                raise ValidationError("You can only set targets for your branch.")
        elif not self.request.user.can_view_all_records:
            target_user = self.request.user
        serializer.save(user=target_user, created_by=self.request.user)

    def perform_update(self, serializer):
        target = self.get_object()
        if not (
            self.request.user.can_view_all_records
            or target.user_id == self.request.user.pk
            or (
                self.request.user.is_branch_manager
                and target.user.branch_id == self.request.user.branch_id
            )
        ):
            raise PermissionDenied("You cannot edit this target.")
        target_user = target.user
        if not self.request.user.can_view_all_records:
            target_user = self.request.user if not self.request.user.is_branch_manager else target.user
        serializer.save(user=target_user)


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    ordering_fields = ["created_at"]

    def get_queryset(self):
        if not getattr(self.request.user, "is_authenticated", False):
            return Notification.objects.none()
        return Notification.objects.filter(user=self.request.user)

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        return Response(self.get_serializer(notification).data)

    @action(detail=False, methods=["post"])
    def read_all(self, request):
        self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({"status": "ok"})
