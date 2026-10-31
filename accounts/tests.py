from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import Branch, User


class BranchStaffDirectoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.lahore = Branch.objects.create(name="Lahore", code="LHR", city="Lahore")
        cls.karachi = Branch.objects.create(name="Karachi", code="KHI", city="Karachi")
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
        cls.lahore_fo = User.objects.create_user(
            username="lahore.fo",
            email="lahore.fo@example.com",
            password="StrongPass!2026",
            first_name="Lahore",
            last_name="Officer",
            role=User.Role.FO,
            branch=cls.lahore,
            is_active=True,
        )
        cls.karachi_fo = User.objects.create_user(
            username="karachi.fo",
            email="karachi.fo@example.com",
            password="StrongPass!2026",
            first_name="Karachi",
            last_name="Officer",
            role=User.Role.FO,
            branch=cls.karachi,
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
        )
        cls.client2 = Client()

    def test_manager_sees_only_branch_staff_in_list_and_export(self):
        self.client2.force_login(self.manager)
        response = self.client2.get(reverse("accounts:user_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.lahore_fo.display_name)
        self.assertNotContains(response, self.karachi_fo.display_name)

        response = self.client2.get(reverse("accounts:user_export"))
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.lahore_fo.display_name, response.content.decode())
        self.assertNotIn(self.karachi_fo.display_name, response.content.decode())

    def test_manager_can_view_branch_user_but_not_other_branch(self):
        self.client2.force_login(self.manager)
        response = self.client2.get(
            reverse("accounts:user_detail", args=[self.lahore_fo.pk])
        )
        self.assertEqual(response.status_code, 200)

        response = self.client2.get(
            reverse("accounts:user_detail", args=[self.karachi_fo.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_manager_has_read_only_staff_directory(self):
        self.client2.force_login(self.manager)
        self.assertEqual(
            self.client2.get(reverse("accounts:user_create")).status_code,
            403,
        )
        self.assertEqual(
            self.client2.get(reverse("accounts:user_edit", args=[self.lahore_fo.pk])).status_code,
            403,
        )

        response = self.client2.get(
            reverse("accounts:user_detail", args=[self.lahore_fo.pk])
        )
        self.assertNotContains(response, reverse("accounts:user_edit", args=[self.lahore_fo.pk]))
        self.assertNotContains(
            response,
            reverse("accounts:user_reset_password", args=[self.lahore_fo.pk]),
        )

    def test_executive_sees_all_users(self):
        self.client2.force_login(self.ceo)
        response = self.client2.get(reverse("accounts:user_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.lahore_fo.display_name)
        self.assertContains(response, self.karachi_fo.display_name)

    def test_fo_cannot_access_staff_directory(self):
        fo = User.objects.create_user(
            username="plain.fo",
            email="plain.fo@example.com",
            password="StrongPass!2026",
            role=User.Role.FO,
            branch=self.lahore,
            is_active=True,
        )
        self.client2.force_login(fo)
        self.assertEqual(self.client2.get(reverse("accounts:user_list")).status_code, 403)


class AuthenticationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.branch = Branch.objects.create(name="Lahore", code="LHR", city="Lahore")
        cls.active = User.objects.create_user(
            username="active.user",
            email="active@example.com",
            password="StrongPass!2026",
            role=User.Role.FO,
            branch=cls.branch,
            is_active=True,
        )
        cls.inactive = User.objects.create_user(
            username="inactive.user",
            email="inactive@example.com",
            password="StrongPass!2026",
            role=User.Role.FO,
            branch=cls.branch,
            is_active=False,
        )

    def test_active_user_can_login(self):
        self.assertTrue(self.client.login(username="active.user", password="StrongPass!2026"))

    def test_inactive_user_cannot_login(self):
        self.assertFalse(self.client.login(username="inactive.user", password="StrongPass!2026"))

    def test_login_form_accepts_email(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "active@example.com", "password": "StrongPass!2026"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("core:dashboard"))


class RootEntryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.branch = Branch.objects.create(name="Lahore", code="LHR", city="Lahore")
        cls.ceo = User.objects.create_user(
            username="root.ceo",
            email="root.ceo@example.com",
            password="StrongPass!2026",
            role=User.Role.CEO,
            is_active=True,
        )

    def test_root_sends_anonymous_users_to_login(self):
        response = self.client.get(reverse("core:home"))
        self.assertRedirects(
            response,
            reverse("accounts:login"),
            fetch_redirect_response=False,
        )

    def test_root_sends_authenticated_users_to_dashboard(self):
        self.client.force_login(self.ceo)
        response = self.client.get(reverse("core:home"))
        self.assertRedirects(
            response,
            reverse("core:dashboard"),
            fetch_redirect_response=False,
        )

    def test_login_page_is_a_private_workspace_entry(self):
        response = self.client.get(reverse("accounts:login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sign in to your account")
        self.assertContains(response, "Secure staff portal")
        self.assertNotContains(response, "A connected real estate network.")
        self.assertNotContains(response, "Everything your team needs")
