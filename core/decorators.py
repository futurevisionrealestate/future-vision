from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def _require(user, predicate):
    if not predicate(user):
        raise PermissionDenied("You do not have permission to access this page.")


def executive_required(view):
    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        _require(request.user, lambda u: u.is_executive)
        return view(request, *args, **kwargs)

    return wrapper


def reviewer_required(view):
    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        _require(
            request.user,
            lambda u: u.can_review_registrations or u.can_final_approve or u.is_executive,
        )
        return view(request, *args, **kwargs)

    return wrapper


def approver_required(view):
    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        _require(
            request.user,
            lambda u: u.can_final_approve or u.is_executive,
        )
        return view(request, *args, **kwargs)

    return wrapper


def reports_required(view):
    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        _require(request.user, lambda u: u.can_access_reports)
        return view(request, *args, **kwargs)

    return wrapper


def manager_or_executive_required(view):
    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        _require(request.user, lambda u: u.is_executive or u.is_branch_manager)
        return view(request, *args, **kwargs)

    return wrapper
