from django.urls import path

from iiif import views

urlpatterns = [
    path("<path:iiif_url>", views.index, name="iiif_endpoint"),
]
