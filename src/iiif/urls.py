from django.urls import path

from . import views

urlpatterns = [
    path("login-link-to-email/", views.send_dataportaal_login_url_to_mail, name='login_link_to_email_endpoint'),
    path("zip/", views.request_multiple_files_in_zip, name='zip_endpoint'),
    path("<path:iiif_url>", views.index, name='iiif_endpoint'),
]
