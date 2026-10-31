from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Branch, User
from crm.models import Client, Deal
from operations.models import DailyTarget, Property


class APIAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.lahore = Branch.objects.create(name="Lahore", code="LHR", city="Lahore")
        cls.karachi = Branch.objects.create(name="Karachi", code="KHI", city="Karachi")
        cls.fo = User.objects.create_user(
            username="fo",
            email="fo@example.com",
            password="StrongPass!2026",
            role=User.Role.FO,
            branch=cls.lahore,
            is_active=True,
        )
        cls.other_fo = User.objects.create_user(
            username="other.fo",
            email="other.fo@example.com",
            password="StrongPass!2026",
            role=User.Role.FO,
            branch=cls.karachi,
            is_active=True,
        )
        cls.manager = User.objects.create_user(
            username="manager",
            email="manager@example.com",
            password="StrongPass!2026",
            role=User.Role.BRANCH_MANAGER,
            branch=cls.lahore,
            is_active=True,
        )
        cls.ceo = User.objects.create_user(
            username="ceo",
            email="ceo@example.com",
            password="StrongPass!2026",
            role=User.Role.CEO,
            is_staff=True,
            is_superuser=True,
            is_active=True,
        )
        cls.own_property = Property.objects.create(
            title="Own Property",
            property_type=Property.Type.HOUSE,
            purpose=Property.Purpose.SALE,
            city="Lahore",
            area="DHA",
            address="DHA",
            contact_name="Owner",
            contact_phone="+923001111111",
            created_by=cls.fo,
            branch=cls.lahore,
            status=Property.Status.APPROVED,
        )
        cls.other_property = Property.objects.create(
            title="Other Property",
            property_type=Property.Type.PLOT,
            purpose=Property.Purpose.SALE,
            city="Karachi",
            area="Clifton",
            address="Clifton",
            contact_name="Owner",
            contact_phone="+923002222222",
            created_by=cls.other_fo,
            branch=cls.karachi,
            status=Property.Status.APPROVED,
        )
        cls.own_client = Client.objects.create(
            name="Own Client",
            phone="+923003333333",
            client_type=Client.Type.BUYER,
            city="Lahore",
            assigned_to=cls.fo,
            created_by=cls.fo,
            branch=cls.lahore,
            status=Client.Status.ACTIVE,
        )
        cls.other_client = Client.objects.create(
            name="Other Client",
            phone="+923004444444",
            client_type=Client.Type.BUYER,
            city="Karachi",
            assigned_to=cls.other_fo,
            created_by=cls.other_fo,
            branch=cls.karachi,
            status=Client.Status.ACTIVE,
        )

    def setUp(self):
        self.api = APIClient()

    def test_me_requires_authentication(self):
        response = self.api.get("/api/v1/me/")
        self.assertEqual(response.status_code, 401)

        self.api.force_authenticate(self.fo)
        response = self.api.get("/api/v1/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["email"], self.fo.email)

    def test_branch_api_is_executive_only(self):
        self.api.force_authenticate(self.fo)
        self.assertEqual(self.api.get("/api/v1/branches/").status_code, 403)

        self.api.force_authenticate(self.ceo)
        self.assertEqual(self.api.get("/api/v1/branches/").status_code, 200)

    def test_property_api_is_scoped_to_user(self):
        self.api.force_authenticate(self.fo)
        response = self.api.get("/api/v1/properties/")
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in response.data["results"]}
        self.assertEqual(ids, {self.own_property.pk})

    def test_manager_property_api_is_scoped_to_branch(self):
        self.api.force_authenticate(self.manager)
        response = self.api.get("/api/v1/properties/")
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in response.data["results"]}
        self.assertEqual(ids, {self.own_property.pk})

    def test_manager_can_edit_branch_property_and_resets_status(self):
        self.api.force_authenticate(self.manager)
        response = self.api.patch(
            f"/api/v1/properties/{self.own_property.pk}/",
            {"title": "Updated by manager"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.own_property.refresh_from_db()
        self.assertEqual(self.own_property.title, "Updated by manager")
        self.assertEqual(self.own_property.status, Property.Status.PENDING)

        response = self.api.patch(
            f"/api/v1/properties/{self.other_property.pk}/",
            {"title": "Cross branch edit"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_property_creation_forces_user_branch_and_pending_status(self):
        self.api.force_authenticate(self.fo)
        response = self.api.post(
            "/api/v1/properties/",
            {
                "title": "API Property",
                "property_type": Property.Type.HOUSE,
                "purpose": Property.Purpose.SALE,
                "branch": self.karachi.pk,
                "city": "Karachi",
                "area": "Clifton",
                "address": "Clifton",
                "contact_name": "Owner",
                "contact_phone": "+923005555555",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        property_obj = Property.objects.get(pk=response.data["id"])
        self.assertEqual(property_obj.created_by, self.fo)
        self.assertEqual(property_obj.branch, self.lahore)
        self.assertEqual(property_obj.status, Property.Status.PENDING)

    def test_deal_api_rejects_cross_branch_property_and_client(self):
        self.api.force_authenticate(self.fo)
        response = self.api.post(
            "/api/v1/deals/",
            {
                "property": self.own_property.pk,
                "client": self.other_client.pk,
                "deal_type": Deal.Type.SALE,
                "amount": "1000000",
                "commission": "10000",
                "deal_date": timezone.localdate().isoformat(),
                "status": Deal.Status.OPEN,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("client", response.data)

    def test_deal_api_rejects_client_outside_scope(self):
        self.api.force_authenticate(self.manager)
        response = self.api.post(
            "/api/v1/deals/",
            {
                "property": self.own_property.pk,
                "client": self.other_client.pk,
                "deal_type": Deal.Type.SALE,
                "amount": "1000000",
                "commission": "10000",
                "deal_date": timezone.localdate().isoformat(),
                "status": Deal.Status.OPEN,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("client", response.data)

    def test_manager_can_create_branch_target_but_not_other_branch_target(self):
        self.api.force_authenticate(self.manager)
        response = self.api.post(
            "/api/v1/targets/",
            {
                "user": self.fo.pk,
                "date": timezone.localdate().isoformat(),
                "target_count": 6,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(
            DailyTarget.objects.filter(user=self.fo, date=timezone.localdate()).exists()
        )

        response = self.api.post(
            "/api/v1/targets/",
            {
                "user": self.other_fo.pk,
                "date": timezone.localdate().isoformat(),
                "target_count": 6,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_schema_endpoint_is_available(self):
        response = self.client.get(reverse("api_schema"))
        self.assertEqual(response.status_code, 200)

