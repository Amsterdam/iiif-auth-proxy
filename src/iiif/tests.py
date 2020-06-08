import logging
from unittest.mock import patch

import pytz
from django.conf import settings
from django.test import Client, SimpleTestCase

from .generate_token import create_token
from .tools import InvalidIIIFUrlError, get_info_from_iiif_url, create_wabo_url
from .views import (RESPONSE_CONTENT_ERROR_RESPONSE_FROM_CANTALOUPE,
                    RESPONSE_CONTENT_ERROR_RESPONSE_FROM_METADATA_SERVER,
                    RESPONSE_CONTENT_NO_DOCUMENT_IN_METADATA,
                    RESPONSE_CONTENT_NO_TOKEN)

log = logging.getLogger(__name__)
timezone = pytz.timezone("UTC")

IMAGE_BINARY_DATA = "image binary data"
PRE_WABO_IMG_URL = "2/edepot:ST-00015-ST00000126_00001.jpg/full/1000,1000/0/default.jpg"
WABO_IMG_URL = "2/wabo:SDZ-38657-4900487_628547/full/1000,1000/0/default.jpg"


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
        response = self.c.get(self.url + PRE_WABO_IMG_URL, **header)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.content.decode("utf-8"), RESPONSE_CONTENT_NO_DOCUMENT_IN_METADATA)

    def test_get_image_when_metadata_server_is_not_available(self):
        header = {'HTTP_AUTHORIZATION': "Bearer " + create_token(settings.BOUWDOSSIER_READ_SCOPE)}
        response = self.c.get(self.url + PRE_WABO_IMG_URL, **header)
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.content.decode("utf-8"), RESPONSE_CONTENT_ERROR_RESPONSE_FROM_METADATA_SERVER)

    @patch('iiif.views.tools.get_meta_data')
    def test_get_image_when_cantaloupe_server_is_not_available(self, mock_get_meta_data):
        # Setting up mocks
        mock_get_meta_data.return_value = MockResponse(
            200,
            json_content={
                'access': settings.ACCESS_PUBLIC,
                'documenten': [{'barcode': 'ST00000126', 'access': settings.ACCESS_PUBLIC}]
            }
        )

        header = {'HTTP_AUTHORIZATION': "Bearer " + create_token(settings.BOUWDOSSIER_READ_SCOPE)}
        response = self.c.get(self.url + PRE_WABO_IMG_URL, **header)
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.content.decode("utf-8"), RESPONSE_CONTENT_ERROR_RESPONSE_FROM_CANTALOUPE)


    @patch('iiif.views.tools.get_image_from_iiif_server')
    @patch('iiif.views.tools.get_meta_data')
    def test_get_public_image_as_non_ambtenaar(self, mock_get_meta_data, mock_get_image_from_iiif_server):
        # Setting up mocks
        mock_get_meta_data.return_value = MockResponse(
            200,
            json_content={
                'access': settings.ACCESS_PUBLIC,
                'documenten': [{'barcode': 'ST00000126', 'access': settings.ACCESS_PUBLIC}]
            }
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200,
            content=IMAGE_BINARY_DATA
        )

        response = self.c.get(self.url + PRE_WABO_IMG_URL)
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
                'documenten': [{'barcode': 'ST00000126', 'access': settings.ACCESS_RESTRICTED}]
            }
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200,
            content=IMAGE_BINARY_DATA
        )

        response = self.c.get(self.url + PRE_WABO_IMG_URL)
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
                'documenten': [{'barcode': 'ST00000126', 'access': settings.ACCESS_RESTRICTED}]
            }
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200,
            content=IMAGE_BINARY_DATA
        )

        response = self.c.get(self.url + PRE_WABO_IMG_URL)
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
                'documenten': [{'barcode': 'ST00000126', 'access': settings.ACCESS_PUBLIC}]
            }
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200,
            content=IMAGE_BINARY_DATA
        )

        response = self.c.get(self.url + PRE_WABO_IMG_URL)
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
                'documenten': [{'barcode': 'ST00000126', 'access': settings.ACCESS_PUBLIC}]
            }
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200,
            content=IMAGE_BINARY_DATA,
            headers={'Content-Type': 'image/png'}
        )

        header = {'HTTP_AUTHORIZATION': "Bearer " + create_token(settings.BOUWDOSSIER_READ_SCOPE)}
        response = self.c.get(self.url + PRE_WABO_IMG_URL, **header)
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
                'documenten': [{'barcode': 'ST00000126', 'access': settings.ACCESS_RESTRICTED}]
            }
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200,
            content=IMAGE_BINARY_DATA,
            headers={'Content-Type': 'image/png'}
        )

        header = {'HTTP_AUTHORIZATION': "Bearer " + create_token(settings.BOUWDOSSIER_READ_SCOPE)}
        response = self.c.get(self.url + PRE_WABO_IMG_URL, **header)
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
                'documenten': [{'barcode': 'ST00000126', 'access': settings.ACCESS_PUBLIC}]
            }
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200,
            content=IMAGE_BINARY_DATA,
            headers={'Content-Type': 'image/png'}
        )

        header = {'HTTP_AUTHORIZATION': "Bearer " + create_token(
            [settings.BOUWDOSSIER_READ_SCOPE, settings.BOUWDOSSIER_EXTENDED_SCOPE])}
        response = self.c.get(self.url + PRE_WABO_IMG_URL, **header)
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
                'documenten': [{'barcode': 'ST00000126', 'access': settings.ACCESS_RESTRICTED}]
            }
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200,
            content=IMAGE_BINARY_DATA,
            headers={'Content-Type': 'image/png'}
        )

        header = {'HTTP_AUTHORIZATION': "Bearer " + create_token(
            [settings.BOUWDOSSIER_READ_SCOPE, settings.BOUWDOSSIER_EXTENDED_SCOPE])}
        response = self.c.get(self.url + PRE_WABO_IMG_URL, **header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode("utf-8"), IMAGE_BINARY_DATA)

    @patch('iiif.views.tools.get_image_from_iiif_server')
    @patch('iiif.views.tools.get_meta_data')
    def test_get_public_dossier_and_restricted_image_as_speciale_ambtenaar(
            self, mock_get_meta_data, mock_get_image_from_iiif_server
    ):
        # Setting up mocks
        mock_get_meta_data.return_value = MockResponse(
            200,
            json_content={
                'access': settings.ACCESS_PUBLIC,
                'documenten': [{'barcode': 'ST00000126', 'access': settings.ACCESS_RESTRICTED}]
            }
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200,
            content=IMAGE_BINARY_DATA,
            headers={'Content-Type': 'image/png'}
        )

        header = {'HTTP_AUTHORIZATION': "Bearer " + create_token(
            [settings.BOUWDOSSIER_READ_SCOPE, settings.BOUWDOSSIER_EXTENDED_SCOPE])}
        response = self.c.get(self.url + PRE_WABO_IMG_URL, **header)
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
                'documenten': [{'barcode': 'ST00000126', 'access': settings.ACCESS_PUBLIC}]
            }
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200,
            content=IMAGE_BINARY_DATA,
            headers={'Content-Type': 'image/png'}
        )

        header = {'HTTP_AUTHORIZATION': "Bearer " + create_token([settings.BOUWDOSSIER_EXTENDED_SCOPE])}
        response = self.c.get(self.url + PRE_WABO_IMG_URL, **header)
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
                'documenten': [{'barcode': 'ST00000126', 'access': settings.ACCESS_RESTRICTED}]
            }
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200,
            content=IMAGE_BINARY_DATA,
            headers={'Content-Type': 'image/png'}
        )

        header = {'HTTP_AUTHORIZATION': "Bearer " + create_token([settings.BOUWDOSSIER_EXTENDED_SCOPE])}
        response = self.c.get(self.url + PRE_WABO_IMG_URL, **header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode("utf-8"), IMAGE_BINARY_DATA)


class ToolsTestCase(SimpleTestCase):
    def test_get_info_from_pre_wabo_url_vanilla(self):
        url_info = get_info_from_iiif_url(PRE_WABO_IMG_URL)
        self.assertEqual(url_info['source'], "edepot")
        self.assertEqual(url_info['stadsdeel'], "ST")
        self.assertEqual(url_info['dossier'], "00015")
        self.assertEqual(url_info['document_barcode'], "ST00000126")
        self.assertEqual(url_info['file'], "00001")

    def test_get_info_from_pre_wabo_url_wrong_formatted_url(self):
        self.assertRaises(InvalidIIIFUrlError, get_info_from_iiif_url, "2/")

    def test_get_info_from_wabo_url_vanilla(self):
        url_info = get_info_from_iiif_url(WABO_IMG_URL)
        self.assertEqual(url_info['source'], "wabo")
        self.assertEqual(url_info['stadsdeel'], "SDZ")
        self.assertEqual(url_info['dossier'], "38657")
        self.assertEqual(url_info['olo'], "4900487")
        self.assertEqual(url_info['document_barcode'], "628547")

    def test_get_info_from_wabo_url_wrong_formatted_url(self):
        self.assertRaises(InvalidIIIFUrlError, get_info_from_iiif_url, "2/")

    def test_create_wabo_url(self):
        url_info = get_info_from_iiif_url(WABO_IMG_URL)
        metadata = {
            'documenten': [
                {
                    'barcode': '628547',
                    'bestanden': [{"filename": "/SDZ/UIT/COH/628547.PDF"}]
                }
            ]
        }

        wabo_url = create_wabo_url(metadata=metadata, url_info=url_info)
        self.assertEqual(wabo_url, '2/wabo:SDZ-UIT-COH-628547.PDF/full/1000,1000/0/default.jpg')
