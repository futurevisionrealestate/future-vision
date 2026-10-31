from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import Branch, FOProfile, User
from core.models import Notification, SiteSetting
from registrations.models import ApprovalLog, RegistrationRequest


class RegistrationWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.lahore = Branch.objects.create(name="Lahore", code="LHR", city="Lahore")
        cls.karachi = Branch.objects.create(name="Karachi", code="KHI", city="Karachi")
        cls.ceo = User.objects.create_user(
            username="ceo",
            email="ceo@example.com",
            password="StrongPass!2026",
            first_name="Chief",
            last_name="Executive",
            role=User.Role.CEO,
            is_staff=True,
            is_superuser=True,
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
        )
        cls.manager = User.objects.create_user(
            username="manager",
            email="manager@example.com",
            password="StrongPass!2026",
            first_name="Branch",
            last_name="Manager",
            role=User.Role.BRANCH_MANAGER,
            branch=cls.lahore,
        )
        cls.applicant = User.objects.create_user(
            username="new.fo",
            email="new.fo@example.com",
            password="StrongPass!2026",
            first_name="New",
            last_name="Officer",
            phone="+923001234567",
            role=User.Role.FO,
            branch=cls.lahore,
            is_active=False,
        )
        cls.registration = RegistrationRequest.objects.create(
            user=cls.applicant,
            applicant_type=RegistrationRequest.ApplicantType.FO,
            source=RegistrationRequest.Source.PUBLIC,
            full_name="New Officer",
            father_name="Senior Officer",
            cnic="35201-1234567-1",
            phone="+923001234567",
            email="new.fo@example.com",
            city="Lahore",
            address="Gulberg",
            branch=cls.lahore,
            education="BBA",
            experience_years=2,
            area="Gulberg",
        )
        cls.client2 = Client()

    def test_public_application_creates_inactive_user_and_pending_request(self):
        response = self.client2.post(
            reverse("accounts:register"),
            {
                "applicant_type": "FO",
                "first_name": "Ayesha",
                "last_name": "Khan",
                "father_name": "Khan",
                "cnic": "35202-7654321-2",
                "phone": "+923009876543",
                "email": "ayesha@example.com",
                "username": "ayesha.fo",
                "password1": "AnotherPass!2026",
                "password2": "AnotherPass!2026",
                "city": "Lahore",
                "address": "DHA",
                "branch": self.lahore.pk,
                "education": "BSc",
                "experience_years": 1,
                "area": "DHA",
                "terms": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        request_obj = RegistrationRequest.objects.get(email="ayesha@example.com")
        self.assertEqual(request_obj.status, RegistrationRequest.Status.PENDING)
        self.assertFalse(request_obj.user.is_active)
        self.assertTrue(request_obj.user.check_password("AnotherPass!2026"))
        self.assertIn(reverse("registrations:status_check"), response["Location"])

    def test_review_then_approve_issues_fv_id_and_activates_user(self):
        self.client2.force_login(self.head_office)
        response = self.client2.post(
            reverse("registrations:review", args=[self.registration.pk]),
            {"notes": "Documents verified."},
        )
        self.assertRedirects(response, self.registration.get_absolute_url())
        self.registration.refresh_from_db()
        self.assertEqual(self.registration.status, RegistrationRequest.Status.UNDER_REVIEW)
        self.assertEqual(self.registration.reviewed_by, self.head_office)

        self.client2.force_login(self.ceo)
        response = self.client2.post(
            reverse("registrations:approve", args=[self.registration.pk]),
            {"notes": "Approved by CEO."},
        )
        self.assertRedirects(response, self.registration.get_absolute_url())
        self.registration.refresh_from_db()
        self.applicant.refresh_from_db()

        self.assertEqual(self.registration.status, RegistrationRequest.Status.APPROVED)
        self.assertEqual(self.registration.approved_by, self.ceo)
        self.assertTrue(self.registration.fv_id_issued.startswith("FVFO-"))
        self.assertEqual(self.applicant.fv_id, self.registration.fv_id_issued)
        self.assertTrue(self.applicant.is_active)
        self.assertTrue(FOProfile.objects.filter(user=self.applicant).exists())
        self.assertEqual(
            ApprovalLog.objects.filter(registration=self.registration).count(),
            2,
        )
        self.assertTrue(
            Notification.objects.filter(user=self.applicant, title="Application approved").exists()
        )

    def test_approval_is_blocked_until_review_when_required(self):
        self.client2.force_login(self.ceo)
        response = self.client2.post(
            reverse("registrations:approve", args=[self.registration.pk]),
        )
        self.assertRedirects(response, self.registration.get_absolute_url())
        self.registration.refresh_from_db()
        self.assertEqual(self.registration.status, RegistrationRequest.Status.PENDING)
        self.assertFalse(self.applicant.is_active)

    def test_ceo_only_mode_blocks_head_office_final_approval(self):
        site = SiteSetting.load()
        site.approval_mode = SiteSetting.ApprovalMode.CEO_ONLY
        site.save()
        self.registration.start_review(self.head_office)
        self.client2.force_login(self.head_office)
        response = self.client2.post(
            reverse("registrations:approve", args=[self.registration.pk]),
        )
        self.assertEqual(response.status_code, 403)

    def test_self_approval_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.registration.approve(self.applicant)

    def test_branch_manager_cannot_view_another_branch_application(self):
        other = User.objects.create_user(
            username="other.fo",
            email="other.fo@example.com",
            password="StrongPass!2026",
            role=User.Role.FO,
            branch=self.karachi,
            is_active=False,
        )
        other_registration = RegistrationRequest.objects.create(
            user=other,
            applicant_type=RegistrationRequest.ApplicantType.FO,
            full_name="Other Officer",
            phone="+923007777777",
            email="other.fo@example.com",
            branch=self.karachi,
        )
        self.client2.force_login(self.manager)
        response = self.client2.get(
            reverse("registrations:detail", args=[other_registration.pk])
        )
        self.assertEqual(response.status_code, 403)

        response = self.client2.get(reverse("registrations:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.registration.request_no)
        self.assertNotContains(response, other_registration.request_no)

    def test_fo_without_application_sees_friendly_status_page(self):
        fo = User.objects.create_user(
            username="direct.fo",
            email="direct.fo@example.com",
            password="StrongPass!2026",
            role=User.Role.FO,
            branch=self.lahore,
            is_active=True,
        )
        self.client2.force_login(fo)
        response = self.client2.get(reverse("registrations:my_application"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No application record on file")
