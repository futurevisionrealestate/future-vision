from django import forms

from core.models import SiteSetting


class StyledFormMixin:
    """Apply consistent classes and helpful input types to every widget."""

    def _style_fields(self):
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "checkbox")
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select")
            elif isinstance(widget, forms.Textarea):
                widget.attrs.setdefault("class", "form-textarea")
                widget.attrs.setdefault("rows", 3)
            else:
                widget.attrs.setdefault("class", "form-input")
            if isinstance(widget, forms.DateInput):
                widget.input_type = "date"
            if isinstance(widget, forms.EmailInput):
                widget.attrs.setdefault("autocomplete", "email")
            if name in {"password", "password1", "password2"}:
                widget.attrs.setdefault("autocomplete", "new-password")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class SiteSettingForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = SiteSetting
        fields = [
            "company_name",
            "tagline",
            "phone",
            "email",
            "address",
            "city",
            "default_daily_target",
            "public_registration_enabled",
            "approval_mode",
            "require_review",
            "maintenance_message",
            "support_hours",
            "facebook_url",
            "instagram_url",
        ]
        widgets = {
            "address": forms.Textarea(attrs={"rows": 2}),
            "maintenance_message": forms.Textarea(attrs={"rows": 2}),
        }

    def clean_default_daily_target(self):
        value = self.cleaned_data["default_daily_target"]
        if value < 1 or value > 100:
            raise forms.ValidationError("Enter a target between 1 and 100.")
        return value
