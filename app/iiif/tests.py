from django.test import TestCase, Client
import logging
import time
from .generate_token import create_token
import pytz
from settings.settings import JWKS_TEST_KEY, EDEPOT_PUBLIC_SCOPE, EDEPOT_PRIVATE_SCOPE

log = logging.getLogger(__name__)
timezone = pytz.timezone("UTC")


class FileTestCase(TestCase):
    def setUp(self):
        self.url = '/iiif/'

        self.c = Client()

    def test_get_public_image_as_speciale_ambtenaar(self):
        """ Test getting a public image as a 'speciale ambtenaar' """

        header = {'HTTP_AUTHORIZATION': "Bearer " + create_token([EDEPOT_PUBLIC_SCOPE, EDEPOT_PRIVATE_SCOPE])}
        response = self.c.get(self.url + "some_public_image.jpg", **header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode("utf-8"), "APPROVED")

    def test_get_public_image_as_normale_ambtenaar(self):
        """ Test getting a public image as a 'normale ambtenaar' """

        header = {'HTTP_AUTHORIZATION': "Bearer " + create_token(EDEPOT_PUBLIC_SCOPE)}
        response = self.c.get(self.url + "some_public_image.jpg", **header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode("utf-8"), "APPROVED IF IMAGE IS PUBLIC")

    def test_get_public_image_as_non_ambtenaar(self):
        """ Test getting a public image as not an ambtenaar """

        header = {'HTTP_AUTHORIZATION': "Bearer " + create_token()}
        response = self.c.get(self.url + "some_public_image.jpg", **header)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.content.decode("utf-8"), "DENIED")
