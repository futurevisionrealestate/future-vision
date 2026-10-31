from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Branch, User
from operations.forms import PropertyForm
from operations.models import DailyTarget, Property


class PropertyScopeAndApprovalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.lahore = Branch.objects.create(name="Lahore", code="LHR", city="Lahore")
        cls.karachi = Branch.objects.create(name="Karachi", code="KHI", city="Karachi")
        cls.fo = User.objects.create_user(
            username="lahore.fo",
            email="lahore.fo@example.com",
            password="StrongPass!2026",
            first_name="Lahore",
            last_name="Officer",
            role=User.Role.FO,
            branch=cls.lahore,
            is_active=True,
        )
        cls.other_fo = User.objects.create_user(
            username="karachi.fo",
            email="karachi.fo@example.com",
            password="StrongPass!2026",
            first_name="Karachi",
            last_name="Officer",
            role=User.Role.FO,
            branch=cls.karachi,
            is_active=True,
        )
        cls.manager = User.objects.create_user(
            username="manager",
            email="manager@example.com",
            password="StrongPass!2026",
            first_name="Branch",
            last_name="Manager",
            role=User.Role.BRANCH_MANAGER,
            branch=cls.lahore,
            is_active=True,
        )
        cls.head_office = User.objects.create_user(
            username="head.office",
            email="head.office@example.com",
            password="StrongPass!2026",
            first_name="Head",
            last_name="Office",
            role=User.Role.HEAD_OFFICE,
            branch=cls.lahore,
            can_review_registrations=True,
            is_active=True,
        )
        cls.ceo = User.objects.create_user(
            username="ceo",
            email="ceo@example.com",
            password="StrongPass!2026",
            first_name="Chief",
            last_name="Executive",
            role=User.Role.CEO,
            is_staff=True,
            is_superuser=True,
            is_active=True,
        )
        cls.lahore_property = Property.objects.create(
            title="Lahore House",
            property_type=Property.Type.HOUSE,
            purpose=Property.Purpose.SALE,
            city="Lahore",
            area="DHA",
            address="DHA Phase 5",
            size_value=5,
            size_unit=Property.SizeUnit.MARLA,
            price=25000000,
            contact_name="Owner",
            contact_phone="+923001111111",
            created_by=cls.fo,
            branch=cls.lahore,
            status=Property.Status.PENDING,
        )
        cls.karachi_property = Property.objects.create(
            title="Karachi Plot",
            property_type=Property.Type.PLOT,
            purpose=Property.Purpose.SALE,
            city="Karachi",
            area="Clifton",
            address="Clifton Block 2",
            size_value=10,
            size_unit=Property.SizeUnit.MARLA,
            price=15000000,
            contact_name="Owner",
            contact_phone="+923002222222",
            created_by=cls.other_fo,
            branch=cls.karachi,
            status=Property.Status.PENDING,
        )
        cls.client2 = Client()

    def test_branch_manager_sees_only_branch_properties(self):
        self.client2.force_login(self.manager)
        response = self.client2.get(reverse("operations:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.lahore_property.title)
        self.assertNotContains(response, self.karachi_property.title)

        response = self.client2.get(
            reverse("operations:detail", args=[self.karachi_property.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_manager_can_edit_branch_property_but_not_other_branch(self):
        self.client2.force_login(self.manager)
        response = self.client2.get(
            reverse("operations:edit", args=[self.lahore_property.pk])
        )
        self.assertEqual(response.status_code, 200)

        response = self.client2.get(
            reverse("operations:edit", args=[self.karachi_property.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_head_office_can_approve_pending_property(self):
        self.client2.force_login(self.head_office)
        response = self.client2.post(
            reverse("operations:approve", args=[self.lahore_property.pk])
        )
        self.assertRedirects(
            response,
            reverse("operations:detail", args=[self.lahore_property.pk]),
        )
        self.lahore_property.refresh_from_db()
        self.assertEqual(self.lahore_property.status, Property.Status.APPROVED)
        self.assertEqual(self.lahore_property.approved_by, self.head_office)

    def test_fo_cannot_approve_property(self):
        self.client2.force_login(self.fo)
        response = self.client2.post(
            reverse("operations:approve", args=[self.lahore_property.pk])
        )
        self.assertEqual(response.status_code, 403)
        self.lahore_property.refresh_from_db()
        self.assertEqual(self.lahore_property.status, Property.Status.PENDING)

    def test_rejection_requires_reason_and_is_scoped(self):
        self.client2.force_login(self.head_office)
        response = self.client2.post(
            reverse("operations:reject", args=[self.lahore_property.pk]),
            {"reason": "No"},
        )
        self.assertRedirects(
            response,
            reverse("operations:detail", args=[self.lahore_property.pk]),
        )
        self.lahore_property.refresh_from_db()
        self.assertEqual(self.lahore_property.status, Property.Status.PENDING)

        response = self.client2.post(
            reverse("operations:reject", args=[self.lahore_property.pk]),
            {"reason": "Contact details could not be verified."},
        )
        self.assertRedirects(
            response,
            reverse("operations:detail", args=[self.lahore_property.pk]),
        )
        self.lahore_property.refresh_from_db()
        self.assertEqual(self.lahore_property.status, Property.Status.REJECTED)
        self.assertIn("could not be verified", self.lahore_property.rejection_reason)

    def test_fo_branch_field_is_locked_to_own_branch(self):
        form = PropertyForm(
            data={
                "title": "Attempted Other Branch",
                "property_type": Property.Type.HOUSE,
                "purpose": Property.Purpose.SALE,
                "branch": self.karachi.pk,
                "city": "Karachi",
                "area": "Clifton",
                "address": "Clifton",
                "size_value": "5",
                "size_unit": Property.SizeUnit.MARLA,
                "price": "1000000",
                "bedrooms": 2,
                "bathrooms": 2,
                "owner_name": "Owner",
                "contact_name": "Owner",
                "contact_phone": "+923003333333",
                "description": "",
                "features": "",
            },
            user=self.fo,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["branch"], self.lahore)


class TargetManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.lahore = Branch.objects.create(name="Lahore", code="LHR", city="Lahore")
        cls.karachi = Branch.objects.create(name="Karachi", code="KHI", city="Karachi")
        cls.manager = User.objects.create_user(
            username="manager",
            email="manager@example.com",
            password="StrongPass!2026",
            role=User.Role.BRANCH_MANAGER,
            branch=cls.lahore,
            is_active=True,
        )
        cls.fo = User.objects.create_user(
            username="lahore.fo",
            email="lahore.fo@example.com",
            password="StrongPass!2026",
            role=User.Role.FO,
            branch=cls.lahore,
            is_active=True,
        )
        cls.other_fo = User.objects.create_user(
            username="karachi.fo",
            email="karachi.fo@example.com",
            password="StrongPass!2026",
            role=User.Role.FO,
            branch=cls.karachi,
            is_active=True,
        )
        cls.client2 = Client()

    def test_manager_can_set_branch_target(self):
        self.client2.force_login(self.manager)
        response = self.client2.post(
            reverse("operations:target_create"),
            {
                "user": self.fo.pk,
                "date": timezone.localdate().isoformat(),
                "target_count": 7,
                "notes": "Branch focus",
            },
        )
        self.assertRedirects(response, reverse("operations:target_list"))
        target = DailyTarget.objects.get(user=self.fo, date=timezone.localdate())
        self.assertEqual(target.target_count, 7)
        self.assertEqual(target.created_by, self.manager)

    def test_manager_cannot_set_target_for_another_branch(self):
        self.client2.force_login(self.manager)
        response = self.client2.post(
            reverse("operations:target_create"),
            {
                "user": self.other_fo.pk,
                "date": timezone.localdate().isoformat(),
                "target_count": 7,
                "notes": "Wrong branch",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            DailyTarget.objects.filter(user=self.other_fo, date=timezone.localdate()).exists()
        )
