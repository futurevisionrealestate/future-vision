import os
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Branch, DealerProfile, FOProfile, User
from core.models import ActivityLog, IDSequence, Notification, SiteSetting
from crm.models import Client, Deal
from operations.models import DailyTarget, Property
from registrations.models import RegistrationRequest


class Command(BaseCommand):
    help = "Create repeatable demo branches, users, properties, clients, deals, and targets."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default=os.getenv("DEMO_PASSWORD", "FutureVision@2026"),
            help="Password for every demo account.",
        )
        parser.add_argument(
            "--reset-passwords",
            action="store_true",
            help="Reset passwords for existing demo accounts.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        password = options["password"]
        reset = options["reset_passwords"]
        today = timezone.localdate()

        site = SiteSetting.load()
        site.company_name = "Future Vision"
        site.tagline = "Real Estate Network & Service Center"
        site.phone = "+92 300 0000000"
        site.email = "info@futurevision.local"
        site.address = "Head Office, Main Boulevard"
        site.city = "Lahore"
        site.default_daily_target = 5
        site.public_registration_enabled = True
        site.require_review = True
        site.approval_mode = SiteSetting.ApprovalMode.AUTHORIZED
        site.support_hours = "Monday to Saturday, 9:00 AM – 7:00 PM"
        site.save()

        branches = {}
        for name, code, city, address, phone in [
            ("Lahore Head Office", "LHR", "Lahore", "Main Boulevard, Gulberg", "+92 42 111 000 001"),
            ("Karachi Branch", "KHI", "Karachi", "Shahrah-e-Faisal", "+92 21 111 000 002"),
            ("Islamabad Branch", "ISB", "Islamabad", "Blue Area, Jinnah Avenue", "+92 51 111 000 003"),
        ]:
            branch, _ = Branch.objects.get_or_create(
                code=code,
                defaults={"name": name, "city": city, "address": address, "phone": phone},
            )
            branch.name = name
            branch.city = city
            branch.address = address
            branch.phone = phone
            branch.is_active = True
            branch.save()
            branches[code] = branch

        def make_user(username, first_name, last_name, email, role, branch, **extra):
            user = User.objects.filter(username=username).first()
            created = user is None
            if created:
                user = User(username=username)
            user.first_name = first_name
            user.last_name = last_name
            user.email = email
            user.role = role
            user.branch = branch
            user.phone = extra.get("phone", "")
            user.is_active = True
            user.is_staff = role in {User.Role.CEO, User.Role.ADMIN}
            user.is_superuser = role in {User.Role.CEO, User.Role.ADMIN}
            user.can_review_registrations = extra.get("can_review", False)
            user.can_final_approve = extra.get("can_approve", False)
            user.approved_at = user.approved_at or timezone.now()
            if role in {User.Role.CEO, User.Role.ADMIN}:
                user.can_review_registrations = True
                user.can_final_approve = True
            if role == User.Role.HEAD_OFFICE:
                user.can_review_registrations = True
            if role in {User.Role.FO, User.Role.DEALER} and not user.fv_id:
                user.fv_id = IDSequence.next("FVFO" if role == User.Role.FO else "FVDE")
            if created or reset:
                user.set_password(password)
            user.save()
            return user

        ceo = make_user(
            "ceo",
            "Future Vision",
            "CEO",
            "ceo@futurevision.local",
            User.Role.CEO,
            branches["LHR"],
            phone="+92 300 1110001",
            can_review=True,
            can_approve=True,
        )
        admin = make_user(
            "admin",
            "System",
            "Administrator",
            "admin@futurevision.local",
            User.Role.ADMIN,
            branches["LHR"],
            phone="+92 300 1110002",
            can_review=True,
            can_approve=True,
        )
        head_office = make_user(
            "headoffice",
            "Head Office",
            "Incharge",
            "headoffice@futurevision.local",
            User.Role.HEAD_OFFICE,
            branches["LHR"],
            phone="+92 300 1110003",
            can_review=True,
        )
        manager = make_user(
            "manager",
            "Lahore",
            "Manager",
            "manager@futurevision.local",
            User.Role.BRANCH_MANAGER,
            branches["LHR"],
            phone="+92 300 1110004",
        )
        fo1 = make_user(
            "fo.ahmed",
            "Ahmed",
            "Raza",
            "ahmed@futurevision.local",
            User.Role.FO,
            branches["LHR"],
            phone="+92 301 2220001",
        )
        fo2 = make_user(
            "fo.sara",
            "Sara",
            "Khan",
            "sara@futurevision.local",
            User.Role.FO,
            branches["LHR"],
            phone="+92 301 2220002",
        )
        dealer = make_user(
            "dealer.hamza",
            "Hamza",
            "Tariq",
            "hamza@futurevision.local",
            User.Role.DEALER,
            branches["KHI"],
            phone="+92 302 3330001",
        )

        branches["LHR"].manager = manager
        branches["LHR"].save(update_fields=["manager", "updated_at"])

        fo1_profile, _ = FOProfile.objects.get_or_create(
            user=fo1,
            defaults={
                "cnic": "35201-1234567-1",
                "education": "BBA",
                "experience_years": 3,
                "area": "Gulberg",
                "city": "Lahore",
                "date_of_joining": today - timedelta(days=120),
                "emergency_contact": "+92 300 9990001",
            },
        )
        fo2_profile, _ = FOProfile.objects.get_or_create(
            user=fo2,
            defaults={
                "cnic": "35201-7654321-2",
                "education": "BSc",
                "experience_years": 2,
                "area": "DHA",
                "city": "Lahore",
                "date_of_joining": today - timedelta(days=80),
            },
        )
        dealer_profile, _ = DealerProfile.objects.get_or_create(
            user=dealer,
            defaults={
                "cnic": "42101-1234567-3",
                "business_name": "Hamza Estates",
                "business_address": "Shahrah-e-Faisal, Karachi",
                "area": "Clifton",
                "city": "Karachi",
                "experience_years": 5,
                "registration_no": "FV-DLR-0001",
            },
        )

        RegistrationRequest.objects.get_or_create(
            user=fo1,
            defaults={
                "applicant_type": RegistrationRequest.ApplicantType.FO,
                "source": RegistrationRequest.Source.ADMIN,
                "full_name": fo1.get_full_name(),
                "father_name": "Raza Ahmed",
                "cnic": fo1_profile.cnic,
                "phone": fo1.phone,
                "email": fo1.email,
                "city": "Lahore",
                "address": "Gulberg, Lahore",
                "branch": fo1.branch,
                "education": fo1_profile.education,
                "experience_years": fo1_profile.experience_years,
                "area": fo1_profile.area,
                "status": RegistrationRequest.Status.APPROVED,
                "reviewed_by": head_office,
                "reviewed_at": timezone.now() - timedelta(days=123),
                "approved_by": ceo,
                "approved_at": timezone.now() - timedelta(days=122),
                "fv_id_issued": fo1.fv_id,
            },
        )
        RegistrationRequest.objects.get_or_create(
            user=fo2,
            defaults={
                "applicant_type": RegistrationRequest.ApplicantType.FO,
                "source": RegistrationRequest.Source.ADMIN,
                "full_name": fo2.get_full_name(),
                "father_name": "Khalid Khan",
                "cnic": fo2_profile.cnic,
                "phone": fo2.phone,
                "email": fo2.email,
                "city": "Lahore",
                "address": "DHA, Lahore",
                "branch": fo2.branch,
                "education": fo2_profile.education,
                "experience_years": fo2_profile.experience_years,
                "area": fo2_profile.area,
                "status": RegistrationRequest.Status.APPROVED,
                "reviewed_by": head_office,
                "reviewed_at": timezone.now() - timedelta(days=83),
                "approved_by": ceo,
                "approved_at": timezone.now() - timedelta(days=82),
                "fv_id_issued": fo2.fv_id,
            },
        )
        RegistrationRequest.objects.get_or_create(
            user=dealer,
            defaults={
                "applicant_type": RegistrationRequest.ApplicantType.DEALER,
                "source": RegistrationRequest.Source.ADMIN,
                "full_name": dealer.get_full_name(),
                "father_name": "Tariq Mahmood",
                "cnic": dealer_profile.cnic,
                "phone": dealer.phone,
                "email": dealer.email,
                "city": "Karachi",
                "address": dealer_profile.business_address,
                "branch": dealer.branch,
                "business_name": dealer_profile.business_name,
                "business_address": dealer_profile.business_address,
                "experience_years": dealer_profile.experience_years,
                "area": dealer_profile.area,
                "status": RegistrationRequest.Status.APPROVED,
                "reviewed_by": head_office,
                "reviewed_at": timezone.now() - timedelta(days=65),
                "approved_by": ceo,
                "approved_at": timezone.now() - timedelta(days=64),
                "fv_id_issued": dealer.fv_id,
            },
        )

        property_seed = [
            {
                "title": "5 Marla House in DHA Phase 5",
                "property_type": Property.Type.HOUSE,
                "purpose": Property.Purpose.SALE,
                "city": "Lahore",
                "area": "DHA Phase 5",
                "address": "Street 12, DHA Phase 5",
                "size_value": Decimal("5"),
                "size_unit": Property.SizeUnit.MARLA,
                "price": Decimal("28500000"),
                "bedrooms": 4,
                "bathrooms": 4,
                "contact_name": "Imran Malik",
                "contact_phone": "+92 300 4440001",
                "owner_name": "Imran Malik",
                "description": "A well-maintained family home with a double-height lounge, modern kitchen, and covered parking.",
                "features": "Corner plot\nMain road access\nNear park\nServant quarter",
                "status": Property.Status.APPROVED,
                "created_by": fo1,
                "days_ago": 4,
            },
            {
                "title": "10 Marla Plot in Bahria Town",
                "property_type": Property.Type.PLOT,
                "purpose": Property.Purpose.SALE,
                "city": "Lahore",
                "area": "Bahria Town",
                "address": "Sector C, Bahria Town",
                "size_value": Decimal("10"),
                "size_unit": Property.SizeUnit.MARLA,
                "price": Decimal("16500000"),
                "contact_name": "Nadeem Akhtar",
                "contact_phone": "+92 300 4440002",
                "owner_name": "Nadeem Akhtar",
                "description": "Ready for construction, close to the main entrance and community mosque.",
                "features": "Possession available\nPark facing\nWide street",
                "status": Property.Status.PENDING,
                "created_by": fo1,
                "days_ago": 1,
            },
            {
                "title": "2 Kanal Farmhouse on Bedian Road",
                "property_type": Property.Type.HOUSE,
                "purpose": Property.Purpose.SALE,
                "city": "Lahore",
                "area": "Bedian Road",
                "address": "Bedian Road, near Ring Road",
                "size_value": Decimal("2"),
                "size_unit": Property.SizeUnit.KANAL,
                "price": Decimal("72000000"),
                "bedrooms": 5,
                "bathrooms": 6,
                "contact_name": "Ayesha Sohail",
                "contact_phone": "+92 300 4440003",
                "owner_name": "Ayesha Sohail",
                "description": "Private farmhouse with a lawn, pool, and separate guest block.",
                "features": "Swimming pool\nLawn\nGuest block\nGated community",
                "status": Property.Status.APPROVED,
                "created_by": fo2,
                "days_ago": 21,
            },
            {
                "title": "Office Floor in Blue Area",
                "property_type": Property.Type.OFFICE,
                "purpose": Property.Purpose.RENT,
                "city": "Islamabad",
                "area": "Blue Area",
                "address": "Jinnah Avenue, Blue Area",
                "size_value": Decimal("1800"),
                "size_unit": Property.SizeUnit.SQFT,
                "price": Decimal("225000"),
                "bedrooms": 0,
                "bathrooms": 3,
                "contact_name": "Bilal Enterprises",
                "contact_phone": "+92 300 4440004",
                "owner_name": "Bilal Enterprises",
                "description": "Furnished office floor with a reception, six workstations, and meeting room.",
                "features": "Furnished\nElevator\nBackup power\nParking",
                "status": Property.Status.RENTED,
                "created_by": fo2,
                "days_ago": 47,
            },
            {
                "title": "1 Kanal House in Model Town",
                "property_type": Property.Type.HOUSE,
                "purpose": Property.Purpose.SALE,
                "city": "Lahore",
                "area": "Model Town",
                "address": "Block C, Model Town",
                "size_value": Decimal("1"),
                "size_unit": Property.SizeUnit.KANAL,
                "price": Decimal("54000000"),
                "bedrooms": 5,
                "bathrooms": 5,
                "contact_name": "Farhan Qureshi",
                "contact_phone": "+92 300 4440005",
                "owner_name": "Farhan Qureshi",
                "description": "Renovated home in a prime location with a large front lawn.",
                "features": "Renovated\nFront lawn\nCorner\nSecurity staff",
                "status": Property.Status.SOLD,
                "created_by": fo1,
                "days_ago": 72,
            },
            {
                "title": "Shop in Johar Town Market",
                "property_type": Property.Type.SHOP,
                "purpose": Property.Purpose.RENT,
                "city": "Lahore",
                "area": "Johar Town",
                "address": "Main Market, Johar Town",
                "size_value": Decimal("450"),
                "size_unit": Property.SizeUnit.SQFT,
                "price": Decimal("85000"),
                "contact_name": "Usman Traders",
                "contact_phone": "+92 300 4440006",
                "owner_name": "Usman Traders",
                "description": "Ground-floor shop with a wide frontage in a high-footfall market.",
                "features": "Ground floor\nWide frontage\nCustomer parking",
                "status": Property.Status.REJECTED,
                "rejection_reason": "Contact number could not be verified. Please update the record and resubmit.",
                "created_by": fo2,
                "days_ago": 12,
            },
        ]

        properties = []
        for item in property_seed:
            item["branch"] = branches[
                "LHR" if item["city"] == "Lahore" else "ISB" if item["city"] == "Islamabad" else "KHI"
            ]
            property_obj = Property.objects.filter(title=item["title"]).first()
            if property_obj is None:
                days_ago = item.pop("days_ago")
                property_obj = Property.objects.create(**item)
                Property.objects.filter(pk=property_obj.pk).update(
                    created_at=timezone.now() - timedelta(days=days_ago)
                )
                property_obj.refresh_from_db()
                if property_obj.status in {Property.Status.APPROVED, Property.Status.SOLD, Property.Status.RENTED}:
                    property_obj.approved_by = ceo
                    property_obj.approved_at = timezone.now() - timedelta(days=max(days_ago - 1, 0))
                    property_obj.save(update_fields=["approved_by", "approved_at", "updated_at"])
            elif property_obj.branch_id != item["branch"].pk:
                property_obj.branch = item["branch"]
                property_obj.save(update_fields=["branch", "updated_at"])
            properties.append(property_obj)

        clients = []
        client_seed = [
            ("Zeeshan Ali", "+92 321 5550001", "zeeshan@example.com", Client.Type.BUYER, "Lahore", "DHA", 20000000, 32000000),
            ("Mahnoor Fatima", "+92 321 5550002", "mahnoor@example.com", Client.Type.TENANT, "Lahore", "Gulberg", 80000, 150000),
            ("Rizwan Ahmed", "+92 321 5550003", "rizwan@example.com", Client.Type.SELLER, "Islamabad", "Blue Area", None, None),
            ("Sadia Noor", "+92 321 5550004", "sadia@example.com", Client.Type.LANDLORD, "Lahore", "Johar Town", None, None),
        ]
        for name, phone, email, client_type, city, area, budget_min, budget_max in client_seed:
            client, _ = Client.objects.get_or_create(
                phone=phone,
                defaults={
                    "name": name,
                    "email": email,
                    "client_type": client_type,
                    "city": city,
                    "area": area,
                    "budget_min": budget_min,
                    "budget_max": budget_max,
                    "requirements": "Looking for a well-maintained property in a secure location.",
                    "source": Client.Source.REFERRAL,
                    "assigned_to": fo1 if client_type in {Client.Type.BUYER, Client.Type.TENANT} else fo2,
                    "branch": branches["LHR"] if city == "Lahore" else branches["ISB"],
                    "created_by": fo1,
                },
            )
            clients.append(client)

        deal_seed = [
            (properties[0], clients[0], Deal.Type.SALE, 27500000, 550000, Deal.Status.NEGOTIATION, fo1, 3),
            (properties[3], clients[1], Deal.Type.RENT, 225000, 112500, Deal.Status.CLOSED_WON, fo2, 14),
            (properties[4], clients[0], Deal.Type.SALE, 53500000, 1070000, Deal.Status.CLOSED_WON, fo1, 20),
        ]
        for property_obj, client, deal_type, amount, commission, status, assigned, days_ago in deal_seed:
            deal = Deal.objects.filter(property=property_obj, client=client).first()
            if deal is None:
                deal = Deal.objects.create(
                    property=property_obj,
                    client=client,
                    deal_type=deal_type,
                    amount=amount,
                    commission=commission,
                    status=status,
                    deal_date=today - timedelta(days=days_ago),
                    assigned_to=assigned,
                    branch=property_obj.branch,
                    created_by=assigned,
                    notes="Demo deal record for pipeline and reporting.",
                )
                if status == Deal.Status.CLOSED_WON:
                    deal.closed_at = timezone.now()
                    deal.save(update_fields=["closed_at", "updated_at"])
                    property_obj.status = Property.Status.SOLD if deal_type == Deal.Type.SALE else Property.Status.RENTED
                    property_obj.save(update_fields=["status", "updated_at"])
                    client.status = Client.Status.CONVERTED
                    client.save(update_fields=["status", "updated_at"])
            elif deal.branch_id != property_obj.branch_id:
                deal.branch = property_obj.branch
                deal.save(update_fields=["branch", "updated_at"])

        for index in range(8):
            target_date = today - timedelta(days=index)
            for fo in (fo1, fo2):
                DailyTarget.objects.get_or_create(
                    user=fo,
                    date=target_date,
                    defaults={"target_count": 5, "created_by": manager},
                )

        pending_email = "pending.fo@futurevision.local"
        pending_user = User.objects.filter(email=pending_email).first()
        if pending_user is None:
            pending_user = User(
                username="pending.fo",
                first_name="Ali",
                last_name="Hassan",
                email=pending_email,
                phone="+92 303 7770001",
                role=User.Role.FO,
                branch=branches["KHI"],
                is_active=False,
            )
            pending_user.set_password(password)
            pending_user.save()
            RegistrationRequest.objects.create(
                user=pending_user,
                applicant_type=RegistrationRequest.ApplicantType.FO,
                source=RegistrationRequest.Source.PUBLIC,
                full_name="Ali Hassan",
                father_name="Hassan Ahmed",
                cnic="42101-8888888-1",
                phone="+92 303 7770001",
                email=pending_email,
                city="Karachi",
                address="North Nazimabad, Karachi",
                branch=branches["KHI"],
                education="BA",
                experience_years=2,
                area="North Nazimabad",
                notes="Interested in joining the Karachi branch.",
            )

        Notification.objects.get_or_create(
            user=ceo,
            title="Demo data is ready",
            defaults={
                "message": "Branches, users, properties, clients, deals, and targets have been loaded.",
                "url": "/dashboard/",
            },
        )
        ActivityLog.objects.get_or_create(
            actor=admin,
            action="demo.seed",
            defaults={
                "description": "Demo dataset created with seed_demo.",
                "model_name": "Demo",
                "object_repr": "Seed data",
            },
        )

        self.stdout.write(self.style.SUCCESS("Demo data ready."))
        self.stdout.write("")
        self.stdout.write("Demo accounts (password: %s)" % password)
        self.stdout.write("  CEO:         ceo / %s" % password)
        self.stdout.write("  Admin:       admin / %s" % password)
        self.stdout.write("  Head Office: headoffice / %s" % password)
        self.stdout.write("  Manager:     manager / %s" % password)
        self.stdout.write("  FO:          fo.ahmed / %s" % password)
        self.stdout.write("  FO:          fo.sara / %s" % password)
        self.stdout.write("  Dealer:      dealer.hamza / %s" % password)
        self.stdout.write("")
        self.stdout.write("Pending application: Ali Hassan (pending.fo) at the Karachi branch.")
