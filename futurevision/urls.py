from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),
    path("accounts/", include("accounts.urls")),
    path("registrations/", include("registrations.urls")),
    path("properties/", include("operations.urls")),
    path("crm/", include("crm.urls")),
    path("api/v1/", include("api.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="api_schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="api_schema"), name="api_docs"),
    path("", include("core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler403 = "accounts.views.permission_denied_view"
handler404 = "accounts.views.page_not_found_view"
handler500 = "accounts.views.server_error_view"
