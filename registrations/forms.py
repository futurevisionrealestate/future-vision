from django import forms

from accounts.models import Branch
from core.forms import StyledFormMixin
from registrations.models import RegistrationRequest


class ReviewForm(StyledFormMixin, forms.Form):
    notes = forms.CharField(
        label="Review notes",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Add review notes..."}),
    )


class RejectForm(StyledFormMixin, forms.Form):
    reason = forms.CharField(
        label="Rejection reason",
        widget=forms.Textarea(
            attrs={"rows": 3, "placeholder": "Explain why this application is being rejected."}
        ),
    )

    def clean_reason(self):
        reason = self.cleaned_data["reason"].strip()
        if len(reason) < 5:
            raise forms.ValidationError("Please provide a clear rejection reason.")
        return reason


class StatusCheckForm(StyledFormMixin, forms.Form):
    request_no = forms.CharField(label="Application number", max_length=30)
    phone_or_cnic = forms.CharField(label="Phone or CNIC", max_length=30)


class RegistrationFilterForm(StyledFormMixin, forms.Form):
    q = forms.CharField(label="Search", required=False)
    status = forms.ChoiceField(
        label="Status",
        required=False,
        choices=[("", "All statuses")] + list(RegistrationRequest.Status.choices),
    )
    applicant_type = forms.ChoiceField(
        label="Applicant type",
        required=False,
        choices=[("", "All types")] + list(RegistrationRequest.ApplicantType.choices),
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
