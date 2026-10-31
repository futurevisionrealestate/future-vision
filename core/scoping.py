from django.db.models import Q


def scope_properties(queryset, user):
    if user.can_view_all_records:
        return queryset
    if user.is_branch_manager:
        return queryset.filter(branch=user.branch) if user.branch else queryset.none()
    return queryset.filter(created_by=user)


def scope_clients(queryset, user):
    if user.can_view_all_records:
        return queryset
    if user.is_branch_manager:
        return queryset.filter(branch=user.branch) if user.branch else queryset.none()
    return queryset.filter(Q(created_by=user) | Q(assigned_to=user))


def scope_deals(queryset, user):
    if user.can_view_all_records:
        return queryset
    if user.is_branch_manager:
        return queryset.filter(branch=user.branch) if user.branch else queryset.none()
    return queryset.filter(Q(created_by=user) | Q(assigned_to=user))


def scope_registrations(queryset, user):
    if user.can_view_all_records:
        return queryset
    if user.is_branch_manager:
        return queryset.filter(branch=user.branch) if user.branch else queryset.none()
    return queryset.filter(user=user)


def scope_targets(queryset, user):
    if user.can_view_all_records:
        return queryset
    if user.is_branch_manager:
        return queryset.filter(user__branch=user.branch) if user.branch else queryset.none()
    return queryset.filter(user=user)


def scope_users(queryset, user):
    if user.can_manage_users:
        return queryset
    if user.is_branch_manager:
        return queryset.filter(branch=user.branch) if user.branch else queryset.none()
    return queryset.filter(pk=user.pk)
