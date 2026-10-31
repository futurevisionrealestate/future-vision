from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone

from accounts.models import DealerProfile, FOProfile
from core.models import ActivityLog, IDSequence, Notification


class RegistrationRequest(models.Model):
    class ApplicantType(models.TextChoices):
        FO = "FO", "Field Officer"
        DEALER = "DEALER", "Dealer"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        UNDER_REVIEW = "UNDER_REVIEW", "Under Review"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    class Source(models.TextChoices):
        PUBLIC = "PUBLIC", "Public application"
        ADMIN = "ADMIN", "Admin created"

    request_no = models.CharField(max_length=30, unique=True, blank=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="registration_request",
    )
    applicant_type = models.CharField(max_length=10, choices=ApplicantType.choices)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.PUBLIC)
    full_name = models.CharField(max_length=160)
    father_name = models.CharField(max_length=120, blank=True)
    cnic = models.CharField(max_length=20, blank=True, db_index=True)
    phone = models.CharField(max_length=30, db_index=True)
    email = models.EmailField()
    city = models.CharField(max_length=80, blank=True)
    address = models.TextField(blank=True)
    branch = models.ForeignKey(
        "accounts.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="registration_requests",
    )
    education = models.CharField(max_length=120, blank=True)
    experience_years = models.PositiveIntegerField(default=0)
    area = models.CharField(max_length=120, blank=True)
    business_name = models.CharField(max_length=160, blank=True)
    business_address = models.TextField(blank=True)
    notes = models.TextField(blank=True, verbose_name="Applicant notes")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_registration_requests",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_registration_requests",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rejected_registration_requests",
    )
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    fv_id_issued = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["applicant_type", "status"]),
            models.Index(fields=["branch", "status"]),
        ]

    def __str__(self):
        return f"{self.request_no} - {self.full_name} ({self.get_applicant_type_display()})"

    def get_absolute_url(self):
        return reverse("registrations:detail", args=[self.pk])

    def save(self, *args, **kwargs):
        if not self.request_no:
            self.request_no = IDSequence.next("FVREQ")
        self.phone = self.phone.strip()
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    @property
    def is_pending(self):
        return self.status in {self.Status.PENDING, self.Status.UNDER_REVIEW}

    @property
    def target_role(self):
        return "FO" if self.applicant_type == self.ApplicantType.FO else "DEALER"

    @property
    def target_id_prefix(self):
        return "FVFO" if self.applicant_type == self.ApplicantType.FO else "FVDE"

    def start_review(self, actor, notes="", request=None):
        if self.status != self.Status.PENDING:
            raise ValidationError("Only pending applications can be moved to review.")
        self.status = self.Status.UNDER_REVIEW
        self.reviewed_by = actor
        self.reviewed_at = timezone.now()
        self.review_notes = notes
        self.save(
            update_fields=[
                "status",
                "reviewed_by",
                "reviewed_at",
                "review_notes",
                "updated_at",
            ]
        )
        ApprovalLog.objects.create(
            registration=self,
            action=ApprovalLog.Action.REVIEW,
            actor=actor,
            notes=notes,
            ip_address=ActivityLog.client_ip(request),
        )
        ActivityLog.log(
            actor,
            "registration.review",
            self,
            f"Started review of {self.request_no}",
            request,
        )
        Notification.notify(
            self.user,
            "Application under review",
            f"Your application {self.request_no} is now under review.",
            reverse("registrations:my_application"),
        )

    def approve(self, actor, notes="", request=None):
        if self.user_id == getattr(actor, "pk", None):
            raise ValidationError("You cannot approve your own registration.")
        if self.user.email and getattr(actor, "email", "").lower() == self.user.email.lower():
            raise ValidationError("You cannot approve your own registration.")
        if self.status not in {self.Status.PENDING, self.Status.UNDER_REVIEW}:
            raise ValidationError("Only pending or under-review applications can be approved.")

        with transaction.atomic():
            locked = RegistrationRequest.objects.select_for_update().get(pk=self.pk)
            if locked.status not in {self.Status.PENDING, self.Status.UNDER_REVIEW}:
                raise ValidationError("This application has already been decided.")

            user = locked.user
            fv_id = user.fv_id or IDSequence.next(locked.target_id_prefix)
            name_parts = locked.full_name.strip().split(" ", 1)
            user.first_name = name_parts[0] if name_parts else ""
            user.last_name = name_parts[1] if len(name_parts) > 1 else ""
            user.role = locked.target_role
            user.branch = locked.branch
            user.fv_id = fv_id
            user.phone = locked.phone
            user.email = locked.email
            user.is_active = True
            user.approved_at = timezone.now()
            user.save(
                update_fields=[
                    "first_name",
                    "last_name",
                    "role",
                    "branch",
                    "fv_id",
                    "phone",
                    "email",
                    "is_active",
                    "approved_at",
                    "updated_at",
                ]
            )

            if locked.applicant_type == self.ApplicantType.FO:
                FOProfile.objects.update_or_create(
                    user=user,
                    defaults={
                        "father_name": locked.father_name,
                        "cnic": locked.cnic,
                        "education": locked.education,
                        "experience_years": locked.experience_years,
                        "area": locked.area,
                        "address": locked.address,
                        "city": locked.city,
                    },
                )
            else:
                DealerProfile.objects.update_or_create(
                    user=user,
                    defaults={
                        "father_name": locked.father_name,
                        "cnic": locked.cnic,
                        "business_name": locked.business_name,
                        "business_address": locked.business_address,
                        "area": locked.area,
                        "city": locked.city,
                        "experience_years": locked.experience_years,
                    },
                )

            locked.status = self.Status.APPROVED
            locked.approved_by = actor
            locked.approved_at = timezone.now()
            locked.fv_id_issued = fv_id
            locked.reviewed_by = locked.reviewed_by or actor
            locked.reviewed_at = locked.reviewed_at or timezone.now()
            locked.save(
                update_fields=[
                    "status",
                    "approved_by",
                    "approved_at",
                    "fv_id_issued",
                    "reviewed_by",
                    "reviewed_at",
                    "updated_at",
                ]
            )

            ApprovalLog.objects.create(
                registration=locked,
                action=ApprovalLog.Action.APPROVE,
                actor=actor,
                notes=notes,
                ip_address=ActivityLog.client_ip(request),
            )
            ActivityLog.log(
                actor,
                "registration.approve",
                locked,
                f"Approved {locked.request_no}; issued {fv_id}",
                request,
            )
            Notification.notify(
                user,
                "Application approved",
                f"Your application was approved. Your ID is {fv_id}.",
                reverse("accounts:login"),
            )
            self.refresh_from_db()

    def reject(self, actor, reason, request=None):
        if self.user_id == getattr(actor, "pk", None):
            raise ValidationError("You cannot reject your own registration.")
        if not reason or not reason.strip():
            raise ValidationError("A rejection reason is required.")
        if self.status not in {self.Status.PENDING, self.Status.UNDER_REVIEW}:
            raise ValidationError("Only pending or under-review applications can be rejected.")

        with transaction.atomic():
            locked = RegistrationRequest.objects.select_for_update().get(pk=self.pk)
            if locked.status not in {self.Status.PENDING, self.Status.UNDER_REVIEW}:
                raise ValidationError("This application has already been decided.")
            locked.status = self.Status.REJECTED
            locked.rejected_by = actor
            locked.rejected_at = timezone.now()
            locked.rejection_reason = reason.strip()
            locked.reviewed_by = locked.reviewed_by or actor
            locked.reviewed_at = locked.reviewed_at or timezone.now()
            locked.save(
                update_fields=[
                    "status",
                    "rejected_by",
                    "rejected_at",
                    "rejection_reason",
                    "reviewed_by",
                    "reviewed_at",
                    "updated_at",
                ]
            )
            locked.user.is_active = False
            locked.user.save(update_fields=["is_active", "updated_at"])
            ApprovalLog.objects.create(
                registration=locked,
                action=ApprovalLog.Action.REJECT,
                actor=actor,
                notes=locked.rejection_reason,
                ip_address=ActivityLog.client_ip(request),
            )
            ActivityLog.log(
                actor,
                "registration.reject",
                locked,
                f"Rejected {locked.request_no}: {locked.rejection_reason}",
                request,
            )
            Notification.notify(
                locked.user,
                "Application rejected",
                f"Your application was rejected. Reason: {locked.rejection_reason}",
                reverse("registrations:status_check"),
            )
            self.refresh_from_db()


class ApprovalLog(models.Model):
    class Action(models.TextChoices):
        REVIEW = "REVIEW", "Review started"
        APPROVE = "APPROVE", "Approved"
        REJECT = "REJECT", "Rejected"

    registration = models.ForeignKey(
        RegistrationRequest,
        on_delete=models.CASCADE,
        related_name="approval_logs",
    )
    action = models.CharField(max_length=20, choices=Action.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="approval_actions",
    )
    notes = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_action_display()} - {self.registration.request_no}"
