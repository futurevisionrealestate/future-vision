from django import forms
from django.forms import inlineformset_factory

from accounts.models import Branch, User
from core.forms import StyledFormMixin
from operations.models import DailyTarget, Property, PropertyImage


class PropertyForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Property
        fields = [
            "title",
            "property_type",
            "purpose",
            "branch",
            "city",
            "area",
            "address",
            "size_value",
            "size_unit",
            "price",
            "bedrooms",
            "bathrooms",
            "owner_name",
            "contact_name",
            "contact_phone",
            "description",
            "features",
        ]
        widgets = {
            "address": forms.Textarea(attrs={"rows": 2}),
            "description": forms.Textarea(attrs={"rows": 4}),
            "features": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["branch"].queryset = Branch.objects.filter(is_active=True)
        if user and not user.can_view_all_records:
            self.fields["branch"].initial = user.branch
            self.fields["branch"].disabled = True
        if user and user.is_branch_manager:
            self.fields["branch"].initial = user.branch
            self.fields["branch"].disabled = True
        if user and not user.is_executive:
            self.fields["branch"].required = False


class PropertyImageForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = PropertyImage
        fields = ["image", "caption", "is_cover"]


PropertyImageFormSet = inlineformset_factory(
    Property,
    PropertyImage,
    form=PropertyImageForm,
    extra=3,
    max_num=8,
    can_delete=True,
)


class PropertyFilterForm(StyledFormMixin, forms.Form):
    q = forms.CharField(label="Search", required=False)
    status = forms.ChoiceField(
        label="Status",
        required=False,
        choices=[("", "All statuses")] + list(Property.Status.choices),
    )
    purpose = forms.ChoiceField(
        label="Purpose",
        required=False,
        choices=[("", "All purposes")] + list(Property.Purpose.choices),
    )
    property_type = forms.ChoiceField(
        label="Property type",
        required=False,
        choices=[("", "All types")] + list(Property.Type.choices),
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


class PropertyRejectForm(StyledFormMixin, forms.Form):
    reason = forms.CharField(
        label="Rejection reason",
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def clean_reason(self):
        reason = self.cleaned_data["reason"].strip()
        if len(reason) < 5:
            raise forms.ValidationError("Please provide a clear rejection reason.")
        return reason


class DailyTargetForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = DailyTarget
        fields = ["user", "date", "target_count", "notes"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["user"].queryset = User.objects.filter(
            role__in=[User.Role.FO, User.Role.DEALER],
            is_active=True,
        )
        if user and user.is_branch_manager:
            self.fields["user"].queryset = self.fields["user"].queryset.filter(branch=user.branch)
        if user and (user.is_fo or user.is_dealer):
            self.fields["user"].initial = user
            self.fields["user"].disabled = True

    def clean_target_count(self):
        value = self.cleaned_data["target_count"]
        if value < 0 or value > 100:
            raise forms.ValidationError("Enter a target between 0 and 100.")
        return value


class TargetFilterForm(StyledFormMixin, forms.Form):
    start = forms.DateField(
        label="From",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    end = forms.DateField(
        label="To",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
