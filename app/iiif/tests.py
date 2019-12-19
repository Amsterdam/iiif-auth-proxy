from django.conf import settings
from django.test import TestCase, Client
import logging
from .generate_token import create_token
import pytz
from .tools import get_info_from_iiif_url, InvalidIIIFUrlError

log = logging.getLogger(__name__)
timezone = pytz.timezone("UTC")


class FileTestCase(TestCase):
    def setUp(self):
        self.url = '/iiif/'
        self.c = Client()

    def test_get_public_image_as_speciale_ambtenaar(self):
        """ Test getting a public image as a 'speciale ambtenaar' """

        header = {'HTTP_AUTHORIZATION': "Bearer " + create_token(
            [settings.BOUWDOSSIER_OPENBAAR_SCOPE, settings.BOUWDOSSIER_ALL_SCOPE])}
        response = self.c.get(self.url + "some_public_image.jpg", **header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode("utf-8"), "APPROVED")

    def test_get_public_image_as_normale_ambtenaar(self):
        """ Test getting a public image as a 'normale ambtenaar' """

        header = {'HTTP_AUTHORIZATION': "Bearer " + create_token(settings.BOUWDOSSIER_OPENBAAR_SCOPE)}
        response = self.c.get(self.url + "some_public_image.jpg", **header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode("utf-8"), "APPROVED IF IMAGE IS PUBLIC")

    def test_get_public_image_as_non_ambtenaar(self):
        """ Test getting a public image as not an ambtenaar """

        header = {'HTTP_AUTHORIZATION': "Bearer " + create_token()}
        response = self.c.get(self.url + "some_public_image.jpg", **header)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.content.decode("utf-8"), "DENIED")


class ToolsTestCase(TestCase):
    def setUp(self):
        self.iiif_url = \
            "https://acc.images.data.amsterdam.nl/iiif/2/" \
            "edepot:ST$00015$ST00000126_00001.jpg/full/1000,1000/0/default.jpg"

    def test_get_info_from_iiif_url_vanilla(self):
        stadsdeel, dossier, subdossier, image = get_info_from_iiif_url(self.iiif_url)
        self.assertEqual(stadsdeel, "ST")
        self.assertEqual(dossier, "00015")
        self.assertEqual(subdossier, "ST00000126")
        self.assertEqual(image, "00001")

    def test_get_info_from_iiif_url_wrong_formatted_url(self):
        self.assertRaises(InvalidIIIFUrlError, get_info_from_iiif_url, "https://acc.images.data.amsterdam.nl/iiif/")
