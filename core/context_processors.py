from django.conf import settings
from django.utils import timezone, translation

from core.i18n import translations
from core.models import Notification, SiteSetting


def site_context(request):
    try:
        site = SiteSetting.load()
    except Exception:
        site = SiteSetting(
            company_name=settings.SITE_NAME,
            tagline=settings.SITE_TAGLINE,
            default_daily_target=settings.DEFAULT_DAILY_TARGET,
        )

    language = translation.get_language() or settings.LANGUAGE_CODE
    context = {
        "site": site,
        "T": translations(language),
        "current_language": language,
        "is_urdu": str(language).startswith("ur"),
        "APP_VERSION": settings.APP_VERSION,
        "today": timezone.localdate(),
    }

    if getattr(request, "user", None) and request.user.is_authenticated:
        unread = Notification.objects.filter(user=request.user, is_read=False)
        context["unread_notifications_count"] = unread.count()
        context["recent_notifications"] = list(unread.order_by("-created_at")[:5])
        try:
            from registrations.models import RegistrationRequest

            pending = RegistrationRequest.objects.filter(
                status__in=[
                    RegistrationRequest.Status.PENDING,
                    RegistrationRequest.Status.UNDER_REVIEW,
                ]
            )
            if not request.user.can_view_all_records:
                if request.user.is_branch_manager:
                    pending = pending.filter(branch=request.user.branch)
                else:
                    pending = pending.none()
            context["pending_approvals_count"] = (
                pending.count()
                if (request.user.can_review_registrations or request.user.can_final_approve)
                else 0
            )
        except Exception:
            context["pending_approvals_count"] = 0

    return context
