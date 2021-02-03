from django.urls import path

from . import views

urlpatterns = [
    path("login-link-to-email/", views.send_dataportaal_login_url_to_burger_email_address, name='login_link_to_email'),
    path("<path:iiif_url>", views.index, name='iiif_endpoint'),
]
