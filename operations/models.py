from decimal import Decimal

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from core.models import ActivityLog, IDSequence, Notification


class Property(models.Model):
    class Type(models.TextChoices):
        HOUSE = "HOUSE", "House"
        PLOT = "PLOT", "Plot"
        SHOP = "SHOP", "Shop"
        OFFICE = "OFFICE", "Office"
        APARTMENT = "APARTMENT", "Apartment"
        AGRICULTURAL = "AGRICULTURAL", "Agricultural"
        OTHER = "OTHER", "Other"

    class Purpose(models.TextChoices):
        SALE = "SALE", "For Sale"
        RENT = "RENT", "For Rent"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PENDING = "PENDING", "Pending approval"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        SOLD = "SOLD", "Sold"
        RENTED = "RENTED", "Rented"
        INACTIVE = "INACTIVE", "Inactive"

    class SizeUnit(models.TextChoices):
        MARLA = "MARLA", "Marla"
        KANAL = "KANAL", "Kanal"
        SQFT = "SQFT", "Square feet"
        SQYD = "SQYD", "Square yards"
        ACRE = "ACRE", "Acre"

    property_code = models.CharField(max_length=30, unique=True, blank=True)
    title = models.CharField(max_length=180)
    property_type = models.CharField(max_length=20, choices=Type.choices)
    purpose = models.CharField(max_length=10, choices=Purpose.choices, default=Purpose.SALE)
    city = models.CharField(max_length=80)
    area = models.CharField(max_length=120)
    address = models.TextField()
    size_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    size_unit = models.CharField(
        max_length=10,
        choices=SizeUnit.choices,
        default=SizeUnit.MARLA,
    )
    price = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        null=True,
        blank=True,
    )
    bedrooms = models.PositiveIntegerField(default=0)
    bathrooms = models.PositiveIntegerField(default=0)
    owner_name = models.CharField(max_length=120, blank=True)
    contact_name = models.CharField(max_length=120)
    contact_phone = models.CharField(max_length=30)
    description = models.TextField(blank=True)
    features = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    rejection_reason = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="properties",
    )
    branch = models.ForeignKey(
        "accounts.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="properties",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_properties",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["branch", "status"]),
            models.Index(fields=["created_by", "created_at"]),
            models.Index(fields=["city", "area"]),
        ]

    def __str__(self):
        return f"{self.property_code} - {self.title}"

    def get_absolute_url(self):
        return reverse("operations:detail", args=[self.pk])

    def save(self, *args, **kwargs):
        if not self.property_code:
            self.property_code = IDSequence.next("FVPR")
        super().save(*args, **kwargs)

    @property
    def price_display(self):
        if self.price is None:
            return "Price on request"
        value = f"{self.price:,.0f}"
        return f"PKR {value}" + (" / month" if self.purpose == self.Purpose.RENT else "")

    @property
    def size_display(self):
        if self.size_value is None:
            return "—"
        return f"{self.size_value:g} {self.get_size_unit_display()}"

    def approve(self, actor, request=None):
        self.status = self.Status.APPROVED
        self.approved_by = actor
        self.approved_at = timezone.now()
        self.rejection_reason = ""
        self.save(
            update_fields=[
                "status",
                "approved_by",
                "approved_at",
                "rejection_reason",
                "updated_at",
            ]
        )
        ActivityLog.log(actor, "property.approve", self, f"Approved {self.property_code}", request)
        Notification.notify(
            self.created_by,
            "Property approved",
            f"Your property {self.property_code} was approved.",
            reverse("operations:detail", args=[self.pk]),
        )

    def reject(self, actor, reason, request=None):
        self.status = self.Status.REJECTED
        self.rejection_reason = reason.strip()
        self.save(update_fields=["status", "rejection_reason", "updated_at"])
        ActivityLog.log(
            actor,
            "property.reject",
            self,
            f"Rejected {self.property_code}: {self.rejection_reason}",
            request,
        )
        Notification.notify(
            self.created_by,
            "Property rejected",
            f"Your property {self.property_code} was rejected. Reason: {self.rejection_reason}",
            reverse("operations:detail", args=[self.pk]),
        )


class PropertyImage(models.Model):
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="images",
    )
    image = models.ImageField(upload_to="properties/%Y/%m/")
    caption = models.CharField(max_length=160, blank=True)
    is_cover = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_cover", "uploaded_at"]

    def __str__(self):
        return f"Image for {self.property.property_code}"


class DailyTarget(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="daily_targets",
    )
    date = models.DateField(default=timezone.localdate)
    target_count = models.PositiveIntegerField(default=5)
    notes = models.CharField(max_length=250, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_daily_targets",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(fields=["user", "date"], name="unique_daily_target"),
        ]
        indexes = [models.Index(fields=["date", "user"])]

    def __str__(self):
        return f"{self.user.display_name} - {self.date} - {self.target_count}"

    @property
    def achieved_count(self):
        return self.user.properties.filter(created_at__date=self.date).exclude(
            status=Property.Status.DRAFT
        ).count()

    @property
    def progress_percent(self):
        if not self.target_count:
            return 0
        return min(100, round(Decimal(self.achieved_count) / Decimal(self.target_count) * 100))

    @property
    def remaining_count(self):
        return max(0, self.target_count - self.achieved_count)
