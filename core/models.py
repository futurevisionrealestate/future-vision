from django.conf import settings
from django.db import models, transaction
from django.urls import reverse


class IDSequence(models.Model):
    prefix = models.CharField(max_length=12, unique=True)
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["prefix"]

    def __str__(self):
        return f"{self.prefix}: {self.last_number}"

    @classmethod
    def next(cls, prefix: str) -> str:
        with transaction.atomic():
            sequence, _ = cls.objects.select_for_update().get_or_create(
                prefix=prefix,
                defaults={"last_number": 0},
            )
            sequence.last_number += 1
            sequence.save(update_fields=["last_number"])
        return f"{prefix}-{sequence.last_number:06d}"


class SiteSetting(models.Model):
    class ApprovalMode(models.TextChoices):
        AUTHORIZED = "AUTHORIZED", "Any authorized final approver"
        CEO_ONLY = "CEO_ONLY", "CEO / System Admin only"

    company_name = models.CharField(max_length=160, default="Future Vision")
    tagline = models.CharField(
        max_length=200,
        default="Real Estate Network & Service Center",
    )
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=80, blank=True)
    default_daily_target = models.PositiveIntegerField(default=5)
    public_registration_enabled = models.BooleanField(default=True)
    approval_mode = models.CharField(
        max_length=20,
        choices=ApprovalMode.choices,
        default=ApprovalMode.AUTHORIZED,
    )
    require_review = models.BooleanField(default=True)
    maintenance_message = models.CharField(max_length=250, blank=True)
    support_hours = models.CharField(max_length=120, blank=True)
    facebook_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Site settings"
        verbose_name_plural = "Site settings"

    def __str__(self):
        return self.company_name

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        settings_obj, _ = cls.objects.get_or_create(pk=1)
        return settings_obj


class ActivityLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
    )
    action = models.CharField(max_length=60)
    model_name = models.CharField(max_length=60, blank=True)
    object_id = models.CharField(max_length=60, blank=True)
    object_repr = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action", "created_at"]),
            models.Index(fields=["actor", "created_at"]),
        ]

    def __str__(self):
        return f"{self.action} by {self.actor or 'system'}"

    @staticmethod
    def client_ip(request):
        if request is None:
            return None
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")

    @classmethod
    def log(cls, actor, action, obj=None, description="", request=None):
        return cls.objects.create(
            actor=actor if getattr(actor, "is_authenticated", False) else None,
            action=action,
            model_name=obj.__class__.__name__ if obj is not None else "",
            object_id=str(obj.pk) if obj is not None and obj.pk else "",
            object_repr=str(obj)[:200] if obj is not None else "",
            description=description,
            ip_address=cls.client_ip(request),
        )


class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    title = models.CharField(max_length=160)
    message = models.TextField(blank=True)
    url = models.CharField(max_length=300, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "is_read", "created_at"])]

    def __str__(self):
        return f"{self.title} -> {self.user}"

    def get_absolute_url(self):
        return self.url or reverse("core:notifications")

    @classmethod
    def notify(cls, user, title, message="", url=""):
        if user is None:
            return None
        return cls.objects.create(user=user, title=title, message=message, url=url)
