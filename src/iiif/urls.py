from django.urls import path

from . import views

urlpatterns = [
    path("<path:iiif_url>", views.index, name='iiif_endpoint'),
]
