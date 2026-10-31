from django.urls import include, path
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework.routers import DefaultRouter

from api.views import (
    BranchViewSet,
    ClientViewSet,
    DailyTargetViewSet,
    DealViewSet,
    MeView,
    NotificationViewSet,
    PropertyViewSet,
    RegistrationRequestViewSet,
    UserViewSet,
)

router = DefaultRouter()
router.register("branches", BranchViewSet, basename="branch")
router.register("users", UserViewSet, basename="user")
router.register("registrations", RegistrationRequestViewSet, basename="registration")
router.register("properties", PropertyViewSet, basename="property")
router.register("clients", ClientViewSet, basename="client")
router.register("deals", DealViewSet, basename="deal")
router.register("targets", DailyTargetViewSet, basename="target")
router.register("notifications", NotificationViewSet, basename="notification")

urlpatterns = [
    path("auth/token/", obtain_auth_token, name="api_token"),
    path("me/", MeView.as_view(), name="api_me"),
    path("", include(router.urls)),
]
