import logging
from unittest.mock import patch

import pytz
from django.conf import settings
from django.test import Client, SimpleTestCase

from .generate_token import create_token
from .tools import InvalidIIIFUrlError, get_info_from_iiif_url
from .views import RESPONSE_CONTENT_NO_TOKEN, RESPONSE_CONTENT_NO_DOCUMENT_IN_METADATA

log = logging.getLogger(__name__)
timezone = pytz.timezone("UTC")

IMAGE_BINARY_DATA = "image binary data"
IMAGE_URL = "2/edepot:ST-00015-ST00000126_00001.jpg/full/1000,1000/0/default.jpg"


class MockResponse:
    def __init__(self, status_code, json_content=None, content=None, headers=None):
        self.status_code = status_code
        self.json_content = json_content
        self.content = content
        self.headers = headers

    def json(self):
        return self.json_content


# We're using SimpleTestCase because the normal TestCase fails because it checks for a DB connection (which is not used)
class FileTestCase(SimpleTestCase):
    def setUp(self):
        self.url = '/iiif/'
        self.c = Client()

    def test_get_image_with_wrongly_formatted_url(self):
        """ Test getting an image with a wrongly formatted url' """

        header = {'HTTP_AUTHORIZATION': "Bearer " + create_token(
            [settings.BOUWDOSSIER_READ_SCOPE, settings.BOUWDOSSIER_EXTENDED_SCOPE])}
        response = self.c.get(self.url + "wrong_formatted_image_url.jpg", **header)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content.decode("utf-8"), "Invalid formatted url")

    @patch('iiif.views.tools.get_image_from_iiif_server')
    @patch('iiif.views.tools.get_meta_data')
    def test_get_image_which_does_not_exist_in_metadata(self, mock_get_meta_data, mock_get_image_from_iiif_server):
        # Setting up mocks
        mock_get_meta_data.return_value = MockResponse(
            200,
            json_content={
                'access': settings.ACCESS_PUBLIC,
                'documenten': []  # This is empty on purpose to test non existing documents in metadata
            }
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200,
            content=IMAGE_BINARY_DATA
        )

        header = {'HTTP_AUTHORIZATION': "Bearer " + create_token(settings.BOUWDOSSIER_READ_SCOPE)}
        response = self.c.get(self.url + IMAGE_URL, **header)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.content.decode("utf-8"), RESPONSE_CONTENT_NO_DOCUMENT_IN_METADATA)

    @patch('iiif.views.tools.get_image_from_iiif_server')
    @patch('iiif.views.tools.get_meta_data')
    def test_get_public_image_as_non_ambtenaar(self, mock_get_meta_data, mock_get_image_from_iiif_server):
        # Setting up mocks
        mock_get_meta_data.return_value = MockResponse(
            200,
            json_content={
                'access': settings.ACCESS_PUBLIC,
                'documenten': [
                    {'barcode': 'ST00000126', 'access': settings.ACCESS_PUBLIC}
                ]
            }
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200,
            content=IMAGE_BINARY_DATA
        )

        response = self.c.get(self.url + IMAGE_URL)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.content.decode("utf-8"), RESPONSE_CONTENT_NO_TOKEN)

    @patch('iiif.views.tools.get_image_from_iiif_server')
    @patch('iiif.views.tools.get_meta_data')
    def test_get_restricted_image_as_non_ambtenaar(self, mock_get_meta_data, mock_get_image_from_iiif_server):
        # Setting up mocks
        mock_get_meta_data.return_value = MockResponse(
            200,
            json_content={
                'access': settings.ACCESS_RESTRICTED,
                'documenten': [
                    {'barcode': 'ST00000126', 'access': settings.ACCESS_RESTRICTED}
                ]
            }
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200,
            content=IMAGE_BINARY_DATA
        )

        response = self.c.get(self.url + IMAGE_URL)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.content.decode("utf-8"), RESPONSE_CONTENT_NO_TOKEN)

    @patch('iiif.views.tools.get_image_from_iiif_server')
    @patch('iiif.views.tools.get_meta_data')
    def test_get_restricted_image_in_public_dossier_as_non_ambtenaar(self, mock_get_meta_data, mock_get_image_from_iiif_server):
        # Setting up mocks
        mock_get_meta_data.return_value = MockResponse(
            200,
            json_content={
                'access': settings.ACCESS_PUBLIC,
                'documenten': [
                    {'barcode': 'ST00000126', 'access': settings.ACCESS_RESTRICTED}
                ]
            }
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200,
            content=IMAGE_BINARY_DATA
        )

        response = self.c.get(self.url + IMAGE_URL)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.content.decode("utf-8"), RESPONSE_CONTENT_NO_TOKEN)

    @patch('iiif.views.tools.get_image_from_iiif_server')
    @patch('iiif.views.tools.get_meta_data')
    def test_get_public_image_in_restricted_dossier_as_non_ambtenaar(self, mock_get_meta_data, mock_get_image_from_iiif_server):
        # Setting up mocks
        mock_get_meta_data.return_value = MockResponse(
            200,
            json_content={
                'access': settings.ACCESS_RESTRICTED,
                'documenten': [
                    {'barcode': 'ST00000126', 'access': settings.ACCESS_PUBLIC}
                ]
            }
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200,
            content=IMAGE_BINARY_DATA
        )

        response = self.c.get(self.url + IMAGE_URL)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.content.decode("utf-8"), RESPONSE_CONTENT_NO_TOKEN)

    @patch('iiif.views.tools.get_image_from_iiif_server')
    @patch('iiif.views.tools.get_meta_data')
    def test_get_public_image_as_normale_ambtenaar(self, mock_get_meta_data, mock_get_image_from_iiif_server):
        # Setting up mocks
        mock_get_meta_data.return_value = MockResponse(
            200,
            json_content={
                'access': settings.ACCESS_PUBLIC,
                'documenten': [
                    {'barcode': 'ST00000126', 'access': settings.ACCESS_PUBLIC}
                ]
            }
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200,
            content=IMAGE_BINARY_DATA,
            headers={'Content-Type': 'image/png'}
        )

        header = {'HTTP_AUTHORIZATION': "Bearer " + create_token(settings.BOUWDOSSIER_READ_SCOPE)}
        response = self.c.get(self.url + IMAGE_URL, **header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode("utf-8"), IMAGE_BINARY_DATA)

    @patch('iiif.views.tools.get_image_from_iiif_server')
    @patch('iiif.views.tools.get_meta_data')
    def test_get_restricted_image_as_normale_ambtenaar(self, mock_get_meta_data, mock_get_image_from_iiif_server):
        # Setting up mocks
        mock_get_meta_data.return_value = MockResponse(
            200,
            json_content={
                'access': settings.ACCESS_RESTRICTED,
                'documenten': [
                    {'barcode': 'ST00000126', 'access': settings.ACCESS_RESTRICTED}
                ]
            }
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200,
            content=IMAGE_BINARY_DATA,
            headers={'Content-Type': 'image/png'}
        )

        header = {'HTTP_AUTHORIZATION': "Bearer " + create_token(settings.BOUWDOSSIER_READ_SCOPE)}
        response = self.c.get(self.url + IMAGE_URL, **header)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.content.decode("utf-8"), "")

    @patch('iiif.views.tools.get_image_from_iiif_server')
    @patch('iiif.views.tools.get_meta_data')
    def test_get_public_image_as_speciale_ambtenaar(self, mock_get_meta_data, mock_get_image_from_iiif_server):
        # Setting up mocks
        mock_get_meta_data.return_value = MockResponse(
            200,
            json_content={
                'access': settings.ACCESS_PUBLIC,
                'documenten': [
                    {'barcode': 'ST00000126', 'access': settings.ACCESS_PUBLIC}
                ]
            }
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200,
            content=IMAGE_BINARY_DATA,
            headers={'Content-Type': 'image/png'}
        )

        header = {'HTTP_AUTHORIZATION': "Bearer " + create_token(
            [settings.BOUWDOSSIER_READ_SCOPE, settings.BOUWDOSSIER_EXTENDED_SCOPE])}
        response = self.c.get(self.url + IMAGE_URL, **header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode("utf-8"), IMAGE_BINARY_DATA)

    @patch('iiif.views.tools.get_image_from_iiif_server')
    @patch('iiif.views.tools.get_meta_data')
    def test_get_restricted_image_as_speciale_ambtenaar(self, mock_get_meta_data, mock_get_image_from_iiif_server):
        # Setting up mocks
        mock_get_meta_data.return_value = MockResponse(
            200,
            json_content={
                'access': settings.ACCESS_RESTRICTED,
                'documenten': [
                    {'barcode': 'ST00000126',
                     'access': settings.ACCESS_RESTRICTED
                     }
                ]
            }
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200,
            content=IMAGE_BINARY_DATA,
            headers={'Content-Type': 'image/png'}
        )

        header = {'HTTP_AUTHORIZATION': "Bearer " + create_token(
            [settings.BOUWDOSSIER_READ_SCOPE, settings.BOUWDOSSIER_EXTENDED_SCOPE])}
        response = self.c.get(self.url + IMAGE_URL, **header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode("utf-8"), IMAGE_BINARY_DATA)



    @patch('iiif.views.tools.get_image_from_iiif_server')
    @patch('iiif.views.tools.get_meta_data')
    def test_get_public_image_with_only_bd_x_scope(self, mock_get_meta_data, mock_get_image_from_iiif_server):
        # Setting up mocks
        mock_get_meta_data.return_value = MockResponse(
            200,
            json_content={
                'access': settings.ACCESS_PUBLIC,
                'documenten': [
                    {'barcode': 'ST00000126', 'access': settings.ACCESS_PUBLIC}
                ]
            }
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200,
            content=IMAGE_BINARY_DATA,
            headers={'Content-Type': 'image/png'}
        )

        header = {'HTTP_AUTHORIZATION': "Bearer " + create_token([settings.BOUWDOSSIER_EXTENDED_SCOPE])}
        response = self.c.get(self.url + IMAGE_URL, **header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode("utf-8"), IMAGE_BINARY_DATA)

    @patch('iiif.views.tools.get_image_from_iiif_server')
    @patch('iiif.views.tools.get_meta_data')
    def test_get_restricted_image_with_only_bd_x_scope(self, mock_get_meta_data, mock_get_image_from_iiif_server):
        # Setting up mocks
        mock_get_meta_data.return_value = MockResponse(
            200,
            json_content={
                'access': settings.ACCESS_RESTRICTED,
                'documenten': [
                    {'barcode': 'ST00000126',
                     'access': settings.ACCESS_RESTRICTED
                     }
                ]
            }
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200,
            content=IMAGE_BINARY_DATA,
            headers={'Content-Type': 'image/png'}
        )

        header = {'HTTP_AUTHORIZATION': "Bearer " + create_token([settings.BOUWDOSSIER_EXTENDED_SCOPE])}
        response = self.c.get(self.url + IMAGE_URL, **header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode("utf-8"), IMAGE_BINARY_DATA)


class ToolsTestCase(SimpleTestCase):
    def setUp(self):
        self.iiif_url = "http://iiif.services.consul/iiif/" + IMAGE_URL

    def test_get_info_from_iiif_url_vanilla(self):
        stadsdeel, dossier, document, file = get_info_from_iiif_url(self.iiif_url)
        self.assertEqual(stadsdeel, "ST")
        self.assertEqual(dossier, "00015")
        self.assertEqual(document, "ST00000126")
        self.assertEqual(file, "00001")

    def test_get_info_from_iiif_url_wrong_formatted_url(self):
        self.assertRaises(InvalidIIIFUrlError, get_info_from_iiif_url, "https://acc.images.data.amsterdam.nl/iiif/")
