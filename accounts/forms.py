import re

from django import forms
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import get_language

from accounts.models import Branch, DealerProfile, FOProfile, User
from core.forms import StyledFormMixin
from core.i18n import translations
from core.models import IDSequence


def normalize_phone(value):
    return re.sub(r"[^\d+]", "", (value or "").strip())


def normalize_cnic(value):
    digits = re.sub(r"\D", "", value or "")
    if not digits:
        return ""
    if len(digits) == 13:
        return f"{digits[:5]}-{digits[5:12]}-{digits[12:]}"
    return digits


class LoginForm(StyledFormMixin, AuthenticationForm):
    username = forms.CharField(
        label="Username or email",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Enter your username or email",
                "autofocus": True,
                "autocomplete": "username",
            }
        ),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={"placeholder": "Enter your password", "autocomplete": "current-password"}
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        t = translations(get_language())
        self.fields["username"].widget.attrs["placeholder"] = t.get(
            "auth_username_placeholder", "Enter your username or email"
        )
        self.fields["password"].widget.attrs["placeholder"] = t.get(
            "auth_password_placeholder", "Enter your password"
        )


class RegistrationApplyForm(StyledFormMixin, forms.Form):
    applicant_type = forms.ChoiceField(
        label="Applicant type",
        choices=[
            ("FO", "Field Officer"),
            ("DEALER", "Dealer"),
        ],
    )
    first_name = forms.CharField(label="First name", max_length=80)
    last_name = forms.CharField(label="Last name", max_length=80, required=False)
    father_name = forms.CharField(label="Father name", max_length=120, required=False)
    cnic = forms.CharField(label="CNIC", max_length=20, required=False)
    phone = forms.CharField(label="Phone", max_length=30)
    email = forms.EmailField(label="Email")
    username = forms.CharField(label="Username", max_length=150)
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput)
    city = forms.CharField(label="City", max_length=80)
    address = forms.CharField(label="Address", widget=forms.Textarea, required=False)
    branch = forms.ModelChoiceField(
        label="Branch",
        queryset=Branch.objects.none(),
        required=False,
        empty_label="Select your branch",
    )
    education = forms.CharField(label="Education", max_length=120, required=False)
    experience_years = forms.IntegerField(label="Experience (years)", min_value=0, initial=0)
    area = forms.CharField(label="Area", max_length=120, required=False)
    business_name = forms.CharField(label="Business name", max_length=160, required=False)
    business_address = forms.CharField(
        label="Business address",
        widget=forms.Textarea,
        required=False,
    )
    notes = forms.CharField(label="Notes", widget=forms.Textarea, required=False)
    terms = forms.BooleanField(
        label="I confirm that the information provided is correct.",
        required=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["branch"].queryset = Branch.objects.filter(is_active=True)

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if not re.match(r"^[\w.@+-]+$", username):
            raise ValidationError("Use letters, numbers, and @ . + - _ only.")
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("This username is already taken.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account already exists with this email.")
        from registrations.models import RegistrationRequest

        if RegistrationRequest.objects.filter(
            email__iexact=email,
            status__in=[
                RegistrationRequest.Status.PENDING,
                RegistrationRequest.Status.UNDER_REVIEW,
            ],
        ).exists():
            raise ValidationError("An application is already pending with this email.")
        return email

    def clean_phone(self):
        phone = normalize_phone(self.cleaned_data["phone"])
        if len(re.sub(r"\D", "", phone)) < 10:
            raise ValidationError("Enter a valid phone number.")
        from registrations.models import RegistrationRequest

        if User.objects.filter(phone=phone, is_active=True).exists():
            raise ValidationError("An active account already uses this phone number.")
        if RegistrationRequest.objects.filter(
            phone=phone,
            status__in=[
                RegistrationRequest.Status.PENDING,
                RegistrationRequest.Status.UNDER_REVIEW,
            ],
        ).exists():
            raise ValidationError("An application is already pending with this phone number.")
        return phone

    def clean_cnic(self):
        cnic = normalize_cnic(self.cleaned_data.get("cnic", ""))
        if cnic and len(re.sub(r"\D", "", cnic)) != 13:
            raise ValidationError("CNIC must contain 13 digits.")
        if cnic:
            from registrations.models import RegistrationRequest

            if RegistrationRequest.objects.filter(
                cnic=cnic,
                status__in=[
                    RegistrationRequest.Status.PENDING,
                    RegistrationRequest.Status.UNDER_REVIEW,
                ],
            ).exists():
                raise ValidationError("An application is already pending with this CNIC.")
        return cnic

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Passwords do not match.")
        if password1:
            temp_user = User(
                username=cleaned.get("username", ""),
                email=cleaned.get("email", ""),
                first_name=cleaned.get("first_name", ""),
                last_name=cleaned.get("last_name", ""),
            )
            from django.contrib.auth.password_validation import validate_password

            try:
                validate_password(password1, temp_user)
            except ValidationError as exc:
                self.add_error("password1", exc)
        if cleaned.get("applicant_type") == "DEALER":
            if not cleaned.get("business_name"):
                self.add_error("business_name", "Business name is required for dealers.")
        return cleaned

    def save(self):
        from registrations.models import RegistrationRequest

        data = self.cleaned_data
        applicant_type = data["applicant_type"]
        with transaction.atomic():
            user = User(
                username=data["username"],
                email=data["email"],
                first_name=data["first_name"].strip(),
                last_name=data["last_name"].strip(),
                phone=data["phone"],
                role=User.Role.FO if applicant_type == "FO" else User.Role.DEALER,
                branch=data.get("branch"),
                is_active=False,
            )
            user.set_password(data["password1"])
            user.save()
            request_obj = RegistrationRequest.objects.create(
                user=user,
                applicant_type=applicant_type,
                source=RegistrationRequest.Source.PUBLIC,
                full_name=f"{user.first_name} {user.last_name}".strip(),
                father_name=data.get("father_name", ""),
                cnic=data.get("cnic", ""),
                phone=data["phone"],
                email=data["email"],
                city=data.get("city", ""),
                address=data.get("address", ""),
                branch=data.get("branch"),
                education=data.get("education", ""),
                experience_years=data.get("experience_years") or 0,
                area=data.get("area", ""),
                business_name=data.get("business_name", ""),
                business_address=data.get("business_address", ""),
                notes=data.get("notes", ""),
            )
        return request_obj


class UserCreateForm(StyledFormMixin, forms.Form):
    username = forms.CharField(max_length=150)
    first_name = forms.CharField(max_length=80)
    last_name = forms.CharField(max_length=80, required=False)
    email = forms.EmailField()
    phone = forms.CharField(max_length=30, required=False)
    role = forms.ChoiceField(choices=User.Role.choices)
    branch = forms.ModelChoiceField(
        queryset=Branch.objects.none(),
        required=False,
        empty_label="No branch",
    )
    can_review_registrations = forms.BooleanField(required=False)
    can_final_approve = forms.BooleanField(required=False)
    is_active = forms.BooleanField(required=False, initial=True)
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["branch"].queryset = Branch.objects.filter(is_active=True)

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("This username is already taken.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account already exists with this email.")
        return email

    def clean_phone(self):
        return normalize_phone(self.cleaned_data.get("phone", ""))

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("password1") != cleaned.get("password2"):
            self.add_error("password2", "Passwords do not match.")
        if cleaned.get("password1"):
            from django.contrib.auth.password_validation import validate_password

            temp = User(
                username=cleaned.get("username", ""),
                email=cleaned.get("email", ""),
                first_name=cleaned.get("first_name", ""),
                last_name=cleaned.get("last_name", ""),
            )
            try:
                validate_password(cleaned["password1"], temp)
            except ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned

    def save(self):
        data = self.cleaned_data
        role = data["role"]
        with transaction.atomic():
            user = User(
                username=data["username"],
                email=data["email"],
                first_name=data["first_name"].strip(),
                last_name=data["last_name"].strip(),
                phone=data.get("phone", ""),
                role=role,
                branch=data.get("branch"),
                can_review_registrations=data["can_review_registrations"],
                can_final_approve=data["can_final_approve"],
                is_active=data["is_active"],
                approved_at=timezone.now() if data["is_active"] else None,
            )
            if role in {User.Role.CEO, User.Role.ADMIN}:
                user.can_review_registrations = True
                user.can_final_approve = True
            if role == User.Role.HEAD_OFFICE:
                user.can_review_registrations = True
            if role in {User.Role.FO, User.Role.DEALER}:
                user.fv_id = IDSequence.next("FVFO" if role == User.Role.FO else "FVDE")
            user.set_password(data["password1"])
            user.save()
            if role == User.Role.FO:
                FOProfile.objects.create(user=user)
            elif role == User.Role.DEALER:
                DealerProfile.objects.create(user=user)
        return user


class UserUpdateForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "phone",
            "role",
            "branch",
            "can_review_registrations",
            "can_final_approve",
            "is_active",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["branch"].queryset = Branch.objects.filter(is_active=True)
        self.fields["branch"].required = False

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exclude(pk=self.instance.pk).exists():
            raise ValidationError("This username is already taken.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise ValidationError("An account already exists with this email.")
        return email

    def clean_phone(self):
        return normalize_phone(self.cleaned_data.get("phone", ""))

    def save(self, commit=True):
        user = super().save(commit=False)
        if user.role in {User.Role.CEO, User.Role.ADMIN}:
            user.can_review_registrations = True
            user.can_final_approve = True
        if user.role in {User.Role.FO, User.Role.DEALER} and not user.fv_id:
            user.fv_id = IDSequence.next("FVFO" if user.role == User.Role.FO else "FVDE")
        if commit:
            user.save()
            if user.role == User.Role.FO and not FOProfile.objects.filter(user=user).exists():
                FOProfile.objects.create(user=user)
            if user.role == User.Role.DEALER and not DealerProfile.objects.filter(user=user).exists():
                DealerProfile.objects.create(user=user)
        return user


class BranchForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Branch
        fields = ["name", "code", "city", "address", "phone", "email", "manager", "is_active"]
        widgets = {"address": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["manager"].queryset = User.objects.filter(
            role__in=[User.Role.BRANCH_MANAGER, User.Role.HEAD_OFFICE],
            is_active=True,
        )
        self.fields["manager"].required = False

    def clean_code(self):
        return self.cleaned_data["code"].strip().upper()


class ProfileForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone"]

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise ValidationError("An account already exists with this email.")
        return email

    def clean_phone(self):
        return normalize_phone(self.cleaned_data.get("phone", ""))


class FOProfileForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = FOProfile
        fields = [
            "father_name",
            "cnic",
            "education",
            "experience_years",
            "area",
            "address",
            "city",
            "date_of_birth",
            "date_of_joining",
            "emergency_contact",
            "notes",
        ]
        widgets = {"address": forms.Textarea(attrs={"rows": 2})}

    def clean_cnic(self):
        return normalize_cnic(self.cleaned_data.get("cnic", ""))


class DealerProfileForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = DealerProfile
        fields = [
            "father_name",
            "cnic",
            "business_name",
            "business_address",
            "area",
            "city",
            "experience_years",
            "registration_no",
            "notes",
        ]
        widgets = {"business_address": forms.Textarea(attrs={"rows": 2})}

    def clean_cnic(self):
        return normalize_cnic(self.cleaned_data.get("cnic", ""))


class AdminPasswordResetForm(StyledFormMixin, SetPasswordForm):
    pass
