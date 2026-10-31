from django.urls import path

from crm import views

app_name = "crm"

urlpatterns = [
    path("clients/", views.client_list, name="client_list"),
    path("clients/export/", views.client_export, name="client_export"),
    path("clients/add/", views.client_create, name="client_create"),
    path("clients/<int:pk>/", views.client_detail, name="client_detail"),
    path("clients/<int:pk>/edit/", views.client_edit, name="client_edit"),
    path("deals/", views.deal_list, name="deal_list"),
    path("deals/export/", views.deal_export, name="deal_export"),
    path("deals/add/", views.deal_create, name="deal_create"),
    path("deals/<int:pk>/", views.deal_detail, name="deal_detail"),
    path("deals/<int:pk>/edit/", views.deal_edit, name="deal_edit"),
]
