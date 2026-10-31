from django import forms

from accounts.models import Branch, User
from core.forms import StyledFormMixin
from crm.models import Client, Deal
from operations.models import Property


class ClientForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Client
        fields = [
            "name",
            "phone",
            "email",
            "client_type",
            "city",
            "area",
            "budget_min",
            "budget_max",
            "requirements",
            "notes",
            "source",
            "status",
            "assigned_to",
            "branch",
        ]
        widgets = {
            "requirements": forms.Textarea(attrs={"rows": 2}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["branch"].queryset = Branch.objects.filter(is_active=True)
        self.fields["assigned_to"].queryset = User.objects.filter(
            is_active=True,
            role__in=[User.Role.FO, User.Role.DEALER, User.Role.BRANCH_MANAGER],
        )
        self.fields["branch"].required = False
        self.fields["assigned_to"].required = False
        if user and not user.can_view_all_records:
            self.fields["branch"].initial = user.branch
            self.fields["branch"].disabled = True
            if user.is_branch_manager:
                self.fields["assigned_to"].queryset = self.fields["assigned_to"].queryset.filter(
                    branch=user.branch
                )
            if user.is_fo or user.is_dealer:
                self.fields["assigned_to"].initial = user
                self.fields["assigned_to"].disabled = True

    def clean(self):
        cleaned = super().clean()
        min_budget = cleaned.get("budget_min")
        max_budget = cleaned.get("budget_max")
        if min_budget and max_budget and min_budget > max_budget:
            self.add_error("budget_max", "Maximum budget must be greater than minimum budget.")
        return cleaned


class DealForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Deal
        fields = [
            "property",
            "client",
            "deal_type",
            "amount",
            "commission",
            "status",
            "deal_date",
            "assigned_to",
            "branch",
            "notes",
        ]
        widgets = {
            "deal_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["property"].queryset = Property.objects.filter(
            status__in=[Property.Status.APPROVED, Property.Status.SOLD, Property.Status.RENTED]
        )
        self.fields["client"].queryset = Client.objects.filter(status=Client.Status.ACTIVE)
        self.fields["assigned_to"].queryset = User.objects.filter(
            is_active=True,
            role__in=[User.Role.FO, User.Role.DEALER, User.Role.BRANCH_MANAGER],
        )
        self.fields["branch"].queryset = Branch.objects.filter(is_active=True)
        self.fields["branch"].required = False
        self.fields["assigned_to"].required = False
        if user and not user.can_view_all_records:
            self.fields["branch"].initial = user.branch
            self.fields["branch"].disabled = True
            self.fields["assigned_to"].queryset = self.fields["assigned_to"].queryset.filter(
                branch=user.branch
            )
            self.fields["property"].queryset = self.fields["property"].queryset.filter(
                branch=user.branch
            )
            self.fields["client"].queryset = self.fields["client"].queryset.filter(
                branch=user.branch
            )
        if user and (user.is_fo or user.is_dealer):
            self.fields["assigned_to"].initial = user
            self.fields["assigned_to"].disabled = True
            self.fields["property"].queryset = self.fields["property"].queryset.filter(
                created_by=user
            )
            self.fields["client"].queryset = self.fields["client"].queryset.filter(
                assigned_to=user
            )

    def clean(self):
        cleaned = super().clean()
        prop = cleaned.get("property")
        client = cleaned.get("client")
        if prop and client and prop.branch and client.branch and prop.branch_id != client.branch_id:
            self.add_error("client", "Property and client must belong to the same branch.")
        return cleaned


class ClientFilterForm(StyledFormMixin, forms.Form):
    q = forms.CharField(label="Search", required=False)
    client_type = forms.ChoiceField(
        label="Client type",
        required=False,
        choices=[("", "All types")] + list(Client.Type.choices),
    )
    status = forms.ChoiceField(
        label="Status",
        required=False,
        choices=[("", "All statuses")] + list(Client.Status.choices),
    )
    branch = forms.ModelChoiceField(
        label="Branch",
        required=False,
        queryset=Branch.objects.none(),
        empty_label="All branches",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["branch"].queryset = Branch.objects.filter(is_active=True)


class DealFilterForm(StyledFormMixin, forms.Form):
    q = forms.CharField(label="Search", required=False)
    status = forms.ChoiceField(
        label="Status",
        required=False,
        choices=[("", "All statuses")] + list(Deal.Status.choices),
    )
    deal_type = forms.ChoiceField(
        label="Deal type",
        required=False,
        choices=[("", "All types")] + list(Deal.Type.choices),
    )
    branch = forms.ModelChoiceField(
        label="Branch",
        required=False,
        queryset=Branch.objects.none(),
        empty_label="All branches",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["branch"].queryset = Branch.objects.filter(is_active=True)
