from django.urls import path

from auth_mail import views

urlpatterns = [
    path(
        "",
        views.send_dataportaal_login_url_to_mail,
        name="login_link_to_email_endpoint",
    ),
]
