from django.urls import path

from zip_consumer import views

urlpatterns = [
    path("zip/", views.request_multiple_files_in_zip, name="zip_endpoint"),
]
