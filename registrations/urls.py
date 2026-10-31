from django.urls import path

from registrations import views

app_name = "registrations"

urlpatterns = [
    path("", views.registration_list, name="list"),
    path("export/", views.registration_export, name="export"),
    path("my-application/", views.my_application, name="my_application"),
    path("status/", views.status_check, name="status_check"),
    path("<int:pk>/", views.registration_detail, name="detail"),
    path("<int:pk>/review/", views.review_registration, name="review"),
    path("<int:pk>/approve/", views.approve_registration, name="approve"),
    path("<int:pk>/reject/", views.reject_registration, name="reject"),
]
