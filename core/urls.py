from django.urls import path

from core import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("notifications/", views.notifications, name="notifications"),
    path("notifications/read-all/", views.mark_all_notifications_read, name="notifications_read_all"),
    path("notifications/<int:pk>/open/", views.open_notification, name="notification_open"),
    path("reports/", views.reports, name="reports"),
    path("audit-logs/", views.audit_logs, name="audit_logs"),
    path("settings/", views.settings_view, name="settings"),
    path("search/", views.search, name="search"),
    path("health/", views.health, name="health"),
]
