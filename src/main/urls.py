"""iiif_auth_proxy URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.urls import include, path

urlpatterns = [
    path("iiif/status/health", include("health.urls")),
    path("iiif/login-link-to-email/", include("auth_mail.urls")),
    path("iiif/zip/", include("zip_consumer.urls")),
    path("iiif/", include("iiif.urls")),
    path("", include("health.urls")),
]
