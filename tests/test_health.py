from unittest import mock

from django.test import Client, SimpleTestCase


class TestViews(SimpleTestCase):
    def setUp(self):
        self.http_client = Client()

    def test_health_view(self):
        response = self.http_client.get("")
        assert response.status_code == 200
        assert response.content == b"Connectivity OK"

    @mock.patch("health.views.settings.DEBUG", True)
    def test_debug_false(self):
        response = self.http_client.get("")
        assert response.status_code == 500
        assert response.content == b"Debug mode not allowed in production"

    def test_health_view_extra_path(self):
        response = self.http_client.get("/iiif/status/health")
        assert response.status_code == 200
        assert response.content == b"Connectivity OK"

    @mock.patch("health.views.settings.DEBUG", True)
    def test_debug_false_extra_path(self):
        response = self.http_client.get("/iiif/status/health")
        assert response.status_code == 500
        assert response.content == b"Debug mode not allowed in production"
