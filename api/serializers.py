from rest_framework import serializers

from accounts.models import Branch, User
from core.models import Notification
from core.scoping import scope_clients, scope_properties
from crm.models import Client, Deal
from operations.models import DailyTarget, Property, PropertyImage
from registrations.models import RegistrationRequest


class BranchSerializer(serializers.ModelSerializer):
    manager_name = serializers.CharField(source="manager.display_name", read_only=True)
    staff_count = serializers.IntegerField(source="active_staff_count", read_only=True)

    class Meta:
        model = Branch
        fields = [
            "id",
            "name",
            "code",
            "city",
            "address",
            "phone",
            "email",
            "manager",
            "manager_name",
            "staff_count",
            "is_active",
            "created_at",
        ]


class UserSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source="get_role_display", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    full_name = serializers.CharField(source="display_name", read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "phone",
            "role",
            "role_display",
            "branch",
            "branch_name",
            "fv_id",
            "can_review_registrations",
            "can_final_approve",
            "is_active",
            "approved_at",
            "date_joined",
        ]
        read_only_fields = [
            "fv_id",
            "approved_at",
            "date_joined",
            "role_display",
            "branch_name",
            "full_name",
        ]


class RegistrationRequestSerializer(serializers.ModelSerializer):
    applicant_type_display = serializers.CharField(
        source="get_applicant_type_display", read_only=True
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    applicant_email = serializers.EmailField(source="user.email", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    reviewed_by_name = serializers.CharField(source="reviewed_by.display_name", read_only=True)
    approved_by_name = serializers.CharField(source="approved_by.display_name", read_only=True)

    class Meta:
        model = RegistrationRequest
        fields = [
            "id",
            "request_no",
            "user",
            "applicant_email",
            "applicant_type",
            "applicant_type_display",
            "full_name",
            "father_name",
            "cnic",
            "phone",
            "email",
            "city",
            "address",
            "branch",
            "branch_name",
            "education",
            "experience_years",
            "area",
            "business_name",
            "business_address",
            "notes",
            "status",
            "status_display",
            "reviewed_by",
            "reviewed_by_name",
            "reviewed_at",
            "review_notes",
            "approved_by",
            "approved_by_name",
            "approved_at",
            "rejection_reason",
            "fv_id_issued",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "request_no",
            "user",
            "status",
            "reviewed_by",
            "reviewed_at",
            "review_notes",
            "approved_by",
            "approved_at",
            "rejection_reason",
            "fv_id_issued",
            "created_at",
            "updated_at",
        ]


class PropertyImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyImage
        fields = ["id", "image", "caption", "is_cover", "uploaded_at"]
        read_only_fields = ["uploaded_at"]


class PropertySerializer(serializers.ModelSerializer):
    property_type_display = serializers.CharField(
        source="get_property_type_display", read_only=True
    )
    purpose_display = serializers.CharField(source="get_purpose_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    created_by_name = serializers.CharField(source="created_by.display_name", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    price_display = serializers.CharField(read_only=True)
    size_display = serializers.CharField(read_only=True)
    images = PropertyImageSerializer(many=True, read_only=True)

    class Meta:
        model = Property
        fields = [
            "id",
            "property_code",
            "title",
            "property_type",
            "property_type_display",
            "purpose",
            "purpose_display",
            "city",
            "area",
            "address",
            "size_value",
            "size_unit",
            "price",
            "price_display",
            "size_display",
            "bedrooms",
            "bathrooms",
            "owner_name",
            "contact_name",
            "contact_phone",
            "description",
            "features",
            "status",
            "status_display",
            "rejection_reason",
            "created_by",
            "created_by_name",
            "branch",
            "branch_name",
            "approved_by",
            "approved_at",
            "is_featured",
            "images",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "property_code",
            "created_by",
            "approved_by",
            "approved_at",
            "rejection_reason",
            "status",
            "created_at",
            "updated_at",
        ]


class ClientSerializer(serializers.ModelSerializer):
    client_type_display = serializers.CharField(
        source="get_client_type_display", read_only=True
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    assigned_to_name = serializers.CharField(source="assigned_to.display_name", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    budget_display = serializers.CharField(read_only=True)

    class Meta:
        model = Client
        fields = [
            "id",
            "client_code",
            "name",
            "phone",
            "email",
            "client_type",
            "client_type_display",
            "city",
            "area",
            "budget_min",
            "budget_max",
            "budget_display",
            "requirements",
            "notes",
            "source",
            "status",
            "status_display",
            "assigned_to",
            "assigned_to_name",
            "branch",
            "branch_name",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["client_code", "created_by", "created_at", "updated_at"]

    def validate_assigned_to(self, value):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if value is None or not user or not user.is_authenticated:
            return value
        if user.is_branch_manager and value.branch_id != user.branch_id:
            raise serializers.ValidationError("You can only assign clients to your branch.")
        if (user.is_fo or user.is_dealer) and value.pk != user.pk:
            raise serializers.ValidationError("You can only assign clients to yourself.")
        return value


class DealSerializer(serializers.ModelSerializer):
    deal_type_display = serializers.CharField(source="get_deal_type_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    property_title = serializers.CharField(source="property.title", read_only=True)
    client_name = serializers.CharField(source="client.name", read_only=True)
    assigned_to_name = serializers.CharField(source="assigned_to.display_name", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)

    class Meta:
        model = Deal
        fields = [
            "id",
            "deal_code",
            "property",
            "property_title",
            "client",
            "client_name",
            "deal_type",
            "deal_type_display",
            "amount",
            "commission",
            "status",
            "status_display",
            "deal_date",
            "closed_at",
            "assigned_to",
            "assigned_to_name",
            "branch",
            "branch_name",
            "created_by",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["deal_code", "created_by", "closed_at", "created_at", "updated_at"]

    def validate(self, attrs):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return attrs
        property_obj = attrs.get("property") or getattr(self.instance, "property", None)
        client_obj = attrs.get("client") or getattr(self.instance, "client", None)
        if property_obj and not scope_properties(
            Property.objects.filter(pk=property_obj.pk), user
        ).exists():
            raise serializers.ValidationError(
                {"property": "You cannot create a deal for this property."}
            )
        if property_obj and property_obj.status not in {
            Property.Status.APPROVED,
            Property.Status.SOLD,
            Property.Status.RENTED,
        }:
            raise serializers.ValidationError(
                {"property": "Only approved, sold, or rented properties can be used in deals."}
            )
        if client_obj and not scope_clients(
            Client.objects.filter(pk=client_obj.pk), user
        ).exists():
            raise serializers.ValidationError(
                {"client": "You cannot create a deal for this client."}
            )
        if (
            property_obj
            and client_obj
            and property_obj.branch_id
            and client_obj.branch_id
            and property_obj.branch_id != client_obj.branch_id
        ):
            raise serializers.ValidationError(
                {"client": "Property and client must belong to the same branch."}
            )
        assigned_to = attrs.get("assigned_to") or getattr(self.instance, "assigned_to", None)
        if assigned_to and user.is_branch_manager and assigned_to.branch_id != user.branch_id:
            raise serializers.ValidationError(
                {"assigned_to": "You can only assign deals within your branch."}
            )
        if assigned_to and (user.is_fo or user.is_dealer) and assigned_to.pk != user.pk:
            raise serializers.ValidationError(
                {"assigned_to": "You can only assign deals to yourself."}
            )
        return attrs


class DailyTargetSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.display_name", read_only=True)
    achieved_count = serializers.IntegerField(read_only=True)
    progress_percent = serializers.IntegerField(read_only=True)
    remaining_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = DailyTarget
        fields = [
            "id",
            "user",
            "user_name",
            "date",
            "target_count",
            "achieved_count",
            "progress_percent",
            "remaining_count",
            "notes",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_by", "created_at", "updated_at"]


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "title", "message", "url", "is_read", "created_at"]
        read_only_fields = ["created_at"]
