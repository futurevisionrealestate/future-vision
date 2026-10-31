from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Branch(models.Model):
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=20, unique=True)
    city = models.CharField(max_length=80)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    manager = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_branches",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"

    @property
    def active_staff_count(self):
        return self.users.filter(is_active=True).count()


class User(AbstractUser):
    class Role(models.TextChoices):
        CEO = "CEO", "CEO"
        ADMIN = "ADMIN", "System Admin"
        HEAD_OFFICE = "HEAD_OFFICE", "Head Office Incharge"
        BRANCH_MANAGER = "BRANCH_MANAGER", "Branch Manager"
        FO = "FO", "Field Officer"
        DEALER = "DEALER", "Dealer"

    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=30, blank=True, db_index=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.FO)
    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
    )
    fv_id = models.CharField(max_length=30, unique=True, null=True, blank=True)
    can_review_registrations = models.BooleanField(default=False)
    can_final_approve = models.BooleanField(default=False)
    must_change_password = models.BooleanField(default=False)
    approved_at = models.DateTimeField(null=True, blank=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["first_name", "last_name", "username"]

    def __str__(self):
        return f"{self.display_name} ({self.get_role_display()})"

    def get_absolute_url(self):
        return reverse("accounts:user_detail", args=[self.pk])

    @property
    def display_name(self):
        full_name = self.get_full_name().strip()
        return full_name or self.username

    @property
    def role_label(self):
        return self.get_role_display()

    @property
    def is_executive(self):
        return self.role in {self.Role.CEO, self.Role.ADMIN}

    @property
    def is_head_office(self):
        return self.role == self.Role.HEAD_OFFICE

    @property
    def is_branch_manager(self):
        return self.role == self.Role.BRANCH_MANAGER

    @property
    def is_fo(self):
        return self.role == self.Role.FO

    @property
    def is_dealer(self):
        return self.role == self.Role.DEALER

    @property
    def can_manage_users(self):
        return self.is_executive

    @property
    def can_manage_branches(self):
        return self.is_executive

    @property
    def can_view_audit(self):
        return self.is_executive

    @property
    def can_access_reports(self):
        return self.is_executive or self.is_head_office or self.is_branch_manager

    @property
    def can_view_all_records(self):
        return self.is_executive or self.is_head_office

    @property
    def can_view_branch_records(self):
        return self.is_branch_manager

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def mark_approved(self, when=None):
        self.is_active = True
        self.approved_at = when or timezone.now()
        self.save(update_fields=["is_active", "approved_at", "updated_at"])


class FOProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="fo_profile")
    father_name = models.CharField(max_length=120, blank=True)
    cnic = models.CharField(max_length=20, blank=True)
    education = models.CharField(max_length=120, blank=True)
    experience_years = models.PositiveIntegerField(default=0)
    area = models.CharField(max_length=120, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=80, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    date_of_joining = models.DateField(null=True, blank=True)
    emergency_contact = models.CharField(max_length=30, blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"FO profile: {self.user.display_name}"


class DealerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="dealer_profile")
    father_name = models.CharField(max_length=120, blank=True)
    cnic = models.CharField(max_length=20, blank=True)
    business_name = models.CharField(max_length=160, blank=True)
    business_address = models.TextField(blank=True)
    area = models.CharField(max_length=120, blank=True)
    city = models.CharField(max_length=80, blank=True)
    experience_years = models.PositiveIntegerField(default=0)
    registration_no = models.CharField(max_length=60, blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"Dealer profile: {self.user.display_name}"
