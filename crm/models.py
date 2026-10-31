from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from core.models import IDSequence


class Client(models.Model):
    class Type(models.TextChoices):
        BUYER = "BUYER", "Buyer"
        SELLER = "SELLER", "Seller"
        TENANT = "TENANT", "Tenant"
        LANDLORD = "LANDLORD", "Landlord"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"
        CONVERTED = "CONVERTED", "Converted"

    class Source(models.TextChoices):
        WALK_IN = "WALK_IN", "Walk-in"
        REFERRAL = "REFERRAL", "Referral"
        SOCIAL = "SOCIAL", "Social media"
        WEBSITE = "WEBSITE", "Website"
        OTHER = "OTHER", "Other"

    client_code = models.CharField(max_length=30, unique=True, blank=True)
    name = models.CharField(max_length=160)
    phone = models.CharField(max_length=30, db_index=True)
    email = models.EmailField(blank=True)
    client_type = models.CharField(max_length=10, choices=Type.choices)
    city = models.CharField(max_length=80)
    area = models.CharField(max_length=120, blank=True)
    budget_min = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        null=True,
        blank=True,
    )
    budget_max = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        null=True,
        blank=True,
    )
    requirements = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.WALK_IN)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clients",
    )
    branch = models.ForeignKey(
        "accounts.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clients",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_clients",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["assigned_to", "status"]),
            models.Index(fields=["branch", "status"]),
        ]

    def __str__(self):
        return f"{self.client_code} - {self.name}"

    def get_absolute_url(self):
        return reverse("crm:client_detail", args=[self.pk])

    def save(self, *args, **kwargs):
        if not self.client_code:
            self.client_code = IDSequence.next("FVCL")
        super().save(*args, **kwargs)

    @property
    def budget_display(self):
        if self.budget_min and self.budget_max:
            return f"PKR {self.budget_min:,.0f} – {self.budget_max:,.0f}"
        if self.budget_max:
            return f"Up to PKR {self.budget_max:,.0f}"
        if self.budget_min:
            return f"From PKR {self.budget_min:,.0f}"
        return "Not specified"


class Deal(models.Model):
    class Type(models.TextChoices):
        SALE = "SALE", "Sale"
        RENT = "RENT", "Rent"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        NEGOTIATION = "NEGOTIATION", "Under negotiation"
        CLOSED_WON = "CLOSED_WON", "Closed won"
        CLOSED_LOST = "CLOSED_LOST", "Closed lost"
        CANCELLED = "CANCELLED", "Cancelled"

    deal_code = models.CharField(max_length=30, unique=True, blank=True)
    property = models.ForeignKey(
        "operations.Property",
        on_delete=models.PROTECT,
        related_name="deals",
    )
    client = models.ForeignKey(
        Client,
        on_delete=models.PROTECT,
        related_name="deals",
    )
    deal_type = models.CharField(max_length=10, choices=Type.choices)
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    commission = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
    )
    deal_date = models.DateField(default=timezone.localdate)
    closed_at = models.DateTimeField(null=True, blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deals",
    )
    branch = models.ForeignKey(
        "accounts.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deals",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_deals",
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-deal_date", "-created_at"]
        indexes = [
            models.Index(fields=["status", "deal_date"]),
            models.Index(fields=["branch", "status"]),
            models.Index(fields=["assigned_to", "status"]),
        ]

    def __str__(self):
        return f"{self.deal_code} - {self.property.title} / {self.client.name}"

    def get_absolute_url(self):
        return reverse("crm:deal_detail", args=[self.pk])

    def save(self, *args, **kwargs):
        if not self.deal_code:
            self.deal_code = IDSequence.next("FVDEAL")
        super().save(*args, **kwargs)
