from django.urls import path

from operations import views

app_name = "operations"

urlpatterns = [
    path("", views.property_list, name="list"),
    path("export/", views.property_export, name="export"),
    path("add/", views.property_create, name="create"),
    path("<int:pk>/", views.property_detail, name="detail"),
    path("<int:pk>/edit/", views.property_edit, name="edit"),
    path("<int:pk>/approve/", views.property_approve, name="approve"),
    path("<int:pk>/reject/", views.property_reject, name="reject"),
    path("targets/", views.target_list, name="target_list"),
    path("targets/add/", views.target_create, name="target_create"),
]
