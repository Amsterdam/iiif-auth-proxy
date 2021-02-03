import json
import logging
from datetime import datetime, timedelta
from unittest.mock import patch

import jwt
import pytz
import time_machine
from django.conf import settings
from django.test import Client, SimpleTestCase

from iiif.generate_token import create_authz_token
from iiif.tools import (RESPONSE_CONTENT_ERROR_RESPONSE_FROM_CANTALOUPE,
                        RESPONSE_CONTENT_ERROR_RESPONSE_FROM_METADATA_SERVER,
                        RESPONSE_CONTENT_NO_DOCUMENT_IN_METADATA,
                        RESPONSE_CONTENT_NO_TOKEN, InvalidIIIFUrlError,
                        create_file_url_and_headers, create_wabo_url,
                        create_mail_login_token, get_info_from_iiif_url)

log = logging.getLogger(__name__)
timezone = pytz.timezone("UTC")

IMAGE_BINARY_DATA = "image binary data"
PRE_WABO_IMG_URL = "2/edepot:ST-00015-ST00000126_00001.jpg/full/1000,1000/0/default.jpg"
PRE_WABO_IMG_URL_X1 = "2/edepot:SQ1452-SQ-01452%20(2)-SQ10079651_00001.jpg/full/1000,1000/0/default.jpg"
PRE_WABO_IMG_URL_X2 = "2/edepot:SQ11426-SQ-file5BAIoi-SQ10092307_00001.jpg/info.json"
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
class FileTestCaseWithAuthz(SimpleTestCase):
    def setUp(self):
        self.url = '/iiif/'
        self.c = Client()

    def test_get_image_with_wrongly_formatted_url(self):
        """ Test getting an image with a wrongly formatted url' """

        header = {'HTTP_AUTHORIZATION': "Bearer " + create_authz_token(
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

        header = {'HTTP_AUTHORIZATION': "Bearer " + create_authz_token(settings.BOUWDOSSIER_READ_SCOPE)}
        response = self.c.get(self.url + PRE_WABO_IMG_URL, **header)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.content.decode("utf-8"), RESPONSE_CONTENT_NO_DOCUMENT_IN_METADATA)

    def test_get_image_when_metadata_server_is_not_available(self):
        header = {'HTTP_AUTHORIZATION': "Bearer " + create_authz_token(settings.BOUWDOSSIER_READ_SCOPE)}
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

        header = {'HTTP_AUTHORIZATION': "Bearer " + create_authz_token(settings.BOUWDOSSIER_READ_SCOPE)}
        response = self.c.get(self.url + PRE_WABO_IMG_URL, **header)
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.content.decode("utf-8"), RESPONSE_CONTENT_ERROR_RESPONSE_FROM_CANTALOUPE)


    @patch('iiif.views.tools.get_image_from_iiif_server')
    @patch('iiif.views.tools.get_meta_data')
    def test_get_public_image_without_token(self, mock_get_meta_data, mock_get_image_from_iiif_server):
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
    def test_get_restricted_image_without_token(self, mock_get_meta_data, mock_get_image_from_iiif_server):
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
    def test_get_restricted_image_in_public_dossier_without_token(self, mock_get_meta_data, mock_get_image_from_iiif_server):
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
    def test_get_public_image_in_restricted_dossier_without_token(self, mock_get_meta_data, mock_get_image_from_iiif_server):
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
    def test_get_public_image_with_read_scope(self, mock_get_meta_data, mock_get_image_from_iiif_server):
        # Setting up mocks
        mock_get_meta_data.return_value = MockResponse(
            200,
            json_content={
                'access': settings.ACCESS_PUBLIC,
                'documenten': [
                    {'barcode': 'ST00000126', 'access': settings.ACCESS_PUBLIC},
                    {'barcode': 'SQ10079651', 'access': settings.ACCESS_PUBLIC},
                    {'barcode': 'SQ10092307', 'access': settings.ACCESS_PUBLIC}
                ]
            }
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200,
            content=IMAGE_BINARY_DATA,
            headers={'Content-Type': 'image/png'}
        )

        header = {'HTTP_AUTHORIZATION': "Bearer " + create_authz_token(settings.BOUWDOSSIER_READ_SCOPE)}
        response = self.c.get(self.url + PRE_WABO_IMG_URL, **header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode("utf-8"), IMAGE_BINARY_DATA)

        response = self.c.get(self.url + PRE_WABO_IMG_URL_X1, **header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode("utf-8"), IMAGE_BINARY_DATA)

        response = self.c.get(self.url + PRE_WABO_IMG_URL_X2, **header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode("utf-8"), IMAGE_BINARY_DATA)


    @patch('iiif.views.tools.get_image_from_iiif_server')
    @patch('iiif.views.tools.get_meta_data')
    def test_get_restricted_image_with_read_scope(self, mock_get_meta_data, mock_get_image_from_iiif_server):
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

        header = {'HTTP_AUTHORIZATION': "Bearer " + create_authz_token(settings.BOUWDOSSIER_READ_SCOPE)}
        response = self.c.get(self.url + PRE_WABO_IMG_URL, **header)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.content.decode("utf-8"), "")

    @patch('iiif.views.tools.get_image_from_iiif_server')
    @patch('iiif.views.tools.get_meta_data')
    def test_get_public_image_with_extended_scope(self, mock_get_meta_data, mock_get_image_from_iiif_server):
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

        header = {'HTTP_AUTHORIZATION': "Bearer " + create_authz_token(
            [settings.BOUWDOSSIER_READ_SCOPE, settings.BOUWDOSSIER_EXTENDED_SCOPE])}
        response = self.c.get(self.url + PRE_WABO_IMG_URL, **header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode("utf-8"), IMAGE_BINARY_DATA)

    @patch('iiif.views.tools.get_image_from_iiif_server')
    @patch('iiif.views.tools.get_meta_data')
    def test_get_restricted_image_with_extended_scope(self, mock_get_meta_data, mock_get_image_from_iiif_server):
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

        header = {'HTTP_AUTHORIZATION': "Bearer " + create_authz_token(
            [settings.BOUWDOSSIER_READ_SCOPE, settings.BOUWDOSSIER_EXTENDED_SCOPE])}
        response = self.c.get(self.url + PRE_WABO_IMG_URL, **header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode("utf-8"), IMAGE_BINARY_DATA)

    @patch('iiif.views.tools.get_image_from_iiif_server')
    @patch('iiif.views.tools.get_meta_data')
    def test_get_public_dossier_and_restricted_image_with_extended_scope(
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

        header = {'HTTP_AUTHORIZATION': "Bearer " + create_authz_token(
            [settings.BOUWDOSSIER_READ_SCOPE, settings.BOUWDOSSIER_EXTENDED_SCOPE])}
        response = self.c.get(self.url + PRE_WABO_IMG_URL, **header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode("utf-8"), IMAGE_BINARY_DATA)


    @patch('iiif.views.tools.get_image_from_iiif_server')
    @patch('iiif.views.tools.get_meta_data')
    def test_get_public_image_with_only_extended_scope_and_no_read_scope(
            self, mock_get_meta_data, mock_get_image_from_iiif_server):
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

        header = {'HTTP_AUTHORIZATION': "Bearer " + create_authz_token([settings.BOUWDOSSIER_EXTENDED_SCOPE])}
        response = self.c.get(self.url + PRE_WABO_IMG_URL, **header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode("utf-8"), IMAGE_BINARY_DATA)

    @patch('iiif.views.tools.get_image_from_iiif_server')
    @patch('iiif.views.tools.get_meta_data')
    def test_get_restricted_image_with_only_extended_scope_and_no_read_scope(
            self, mock_get_meta_data, mock_get_image_from_iiif_server):
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

        header = {'HTTP_AUTHORIZATION': "Bearer " + create_authz_token([settings.BOUWDOSSIER_EXTENDED_SCOPE])}
        response = self.c.get(self.url + PRE_WABO_IMG_URL, **header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode("utf-8"), IMAGE_BINARY_DATA)


class FileTestCaseWithMailJWT(SimpleTestCase):
    def setUp(self):
        self.file_url = '/iiif/'
        self.login_link_url = '/iiif/login-link-to-email/'
        self.c = Client()
        self.test_email_address = 'jwttest@amsterdam.nl'
        self.mail_login_token = create_mail_login_token(self.test_email_address, settings.SECRET_KEY)

    @patch('iiif.views.tools.send_email')
    def test_send_dataportaal_login_url_to_burger_email_address(self, mock_send_email):
        mock_send_email.return_value = None  # Prevent it from sending actual emails
        payload = {'email': 'burger@amsterdam.nl'}
        response = self.c.post(self.login_link_url, json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)

    def test_login_url_to_burger_fails_on_other_than_post(self):
        response = self.c.get(self.login_link_url)
        self.assertEqual(response.status_code, 405)
        response = self.c.put(self.login_link_url)
        self.assertEqual(response.status_code, 405)
        response = self.c.delete(self.login_link_url)
        self.assertEqual(response.status_code, 405)

    def test_request_with_invalid_json_fails(self):
        response = self.c.post(self.login_link_url, "invalid json", content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_request_with_missing_email_address_field_fails(self):
        response = self.c.post(self.login_link_url, json.dumps({'something': 'else'}), content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_request_with_invalid_email_address_fails(self):
        # Missing @
        payload = {'email': 'burgeramsterdam.nl'}
        response = self.c.post(self.login_link_url, json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 400)

        # Missing dot
        payload = {'email': 'burger@amsterdamnl'}
        response = self.c.post(self.login_link_url, json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 400)

    @patch('iiif.views.tools.get_image_from_iiif_server')
    @patch('iiif.views.tools.get_meta_data')
    def test_get_public_image_with_read_scope(self, mock_get_meta_data, mock_get_image_from_iiif_server):
        # Setting up mocks
        mock_get_meta_data.return_value = MockResponse(
            200,
            json_content={
                'access': settings.ACCESS_PUBLIC,
                'documenten': [
                    {'barcode': 'ST00000126', 'access': settings.ACCESS_PUBLIC},
                    {'barcode': 'SQ10079651', 'access': settings.ACCESS_PUBLIC},
                    {'barcode': 'SQ10092307', 'access': settings.ACCESS_PUBLIC}
                ]
            }
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200,
            content=IMAGE_BINARY_DATA,
            headers={'Content-Type': 'image/png'}
        )

        response = self.c.get(self.file_url + PRE_WABO_IMG_URL + '?auth=' + self.mail_login_token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode("utf-8"), IMAGE_BINARY_DATA)

        response = self.c.get(self.file_url + PRE_WABO_IMG_URL_X1 + '?auth=' + self.mail_login_token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode("utf-8"), IMAGE_BINARY_DATA)

        response = self.c.get(self.file_url + PRE_WABO_IMG_URL_X2 + '?auth=' + self.mail_login_token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode("utf-8"), IMAGE_BINARY_DATA)

    @patch('iiif.views.tools.get_image_from_iiif_server')
    @patch('iiif.views.tools.get_meta_data')
    def test_get_restricted_image_with_read_scope(self, mock_get_meta_data, mock_get_image_from_iiif_server):
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

        response = self.c.get(self.file_url + PRE_WABO_IMG_URL + '?auth=' + self.mail_login_token)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.content.decode("utf-8"), "")

    @patch('iiif.views.tools.get_image_from_iiif_server')
    @patch('iiif.views.tools.get_meta_data')
    def test_get_public_image_with_expired_token(self, mock_get_meta_data, mock_get_image_from_iiif_server):
        # Setting up mocks
        mock_get_meta_data.return_value = MockResponse(
            200,
            json_content={
                'access': settings.ACCESS_PUBLIC,
                'documenten': [
                    {'barcode': 'ST00000126', 'access': settings.ACCESS_PUBLIC},
                    {'barcode': 'SQ10079651', 'access': settings.ACCESS_PUBLIC},
                    {'barcode': 'SQ10092307', 'access': settings.ACCESS_PUBLIC}
                ]
            }
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200,
            content=IMAGE_BINARY_DATA,
            headers={'Content-Type': 'image/png'}
        )

        # Time travel to two days ago so that the jwt token will be invalid
        with time_machine.travel(datetime.now() - timedelta(days=2)):
            jwt_token = create_mail_login_token(self.test_email_address, settings.SECRET_KEY)

        response = self.c.get(self.file_url + PRE_WABO_IMG_URL + '?auth=' + jwt_token)
        self.assertEqual(response.status_code, 401)

    @patch('iiif.views.tools.get_image_from_iiif_server')
    @patch('iiif.views.tools.get_meta_data')
    def test_get_public_image_with_invalid_token_signature(self, mock_get_meta_data, mock_get_image_from_iiif_server):
        # Setting up mocks
        mock_get_meta_data.return_value = MockResponse(
            200,
            json_content={
                'access': settings.ACCESS_PUBLIC,
                'documenten': [
                    {'barcode': 'ST00000126', 'access': settings.ACCESS_PUBLIC},
                    {'barcode': 'SQ10079651', 'access': settings.ACCESS_PUBLIC},
                    {'barcode': 'SQ10092307', 'access': settings.ACCESS_PUBLIC}
                ]
            }
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200,
            content=IMAGE_BINARY_DATA,
            headers={'Content-Type': 'image/png'}
        )
        mail_login_token = create_mail_login_token(self.test_email_address, 'invalid_key')
        response = self.c.get(self.file_url + PRE_WABO_IMG_URL + '?auth=' + mail_login_token)
        self.assertEqual(response.status_code, 401)


class ToolsTestCase(SimpleTestCase):
    def test_get_info_from_pre_wabo_url_vanilla(self):
        url_info = get_info_from_iiif_url(PRE_WABO_IMG_URL, False)
        self.assertEqual(url_info['source'], "edepot")
        self.assertEqual(url_info['stadsdeel'], "ST")
        self.assertEqual(url_info['dossier'], "00015")
        self.assertEqual(url_info['document_barcode'], "ST00000126")
        self.assertEqual(url_info['file'], "00001")
        self.assertEqual(url_info['source_file'], False)

    def test_get_info_from_pre_wabo_url_with_source_file(self):
        url_info = get_info_from_iiif_url(PRE_WABO_IMG_URL, True)
        self.assertEqual(url_info['source'], "edepot")
        self.assertEqual(url_info['stadsdeel'], "ST")
        self.assertEqual(url_info['dossier'], "00015")
        self.assertEqual(url_info['document_barcode'], "ST00000126")
        self.assertEqual(url_info['file'], "00001")
        self.assertEqual(url_info['source_file'], True)

    def test_get_info_from_pre_wabo_url_wrong_formatted_url(self):
        self.assertRaises(InvalidIIIFUrlError, get_info_from_iiif_url, "2/", False)

    def test_get_info_from_wabo_url_vanilla(self):
        url_info = get_info_from_iiif_url(WABO_IMG_URL, False)
        self.assertEqual(url_info['source'], "wabo")
        self.assertEqual(url_info['stadsdeel'], "SDZ")
        self.assertEqual(url_info['dossier'], "38657")
        self.assertEqual(url_info['olo'], "4900487")
        self.assertEqual(url_info['document_barcode'], "628547")
        self.assertEqual(url_info['source_file'], False)

    def test_get_info_from_wabo_url_with_source_file(self):
        url_info = get_info_from_iiif_url(WABO_IMG_URL, True)
        self.assertEqual(url_info['source'], "wabo")
        self.assertEqual(url_info['stadsdeel'], "SDZ")
        self.assertEqual(url_info['dossier'], "38657")
        self.assertEqual(url_info['olo'], "4900487")
        self.assertEqual(url_info['document_barcode'], "628547")
        self.assertEqual(url_info['source_file'], True)

    def test_get_info_from_wabo_url_with_underscores_in_barcode(self):
        url_info = get_info_from_iiif_url("2/wabo:SDO-10316333-3304_ECS0000004420_000_000/info.json", False)
        self.assertEqual(url_info['source'], "wabo")
        self.assertEqual(url_info['stadsdeel'], "SDO")
        self.assertEqual(url_info['dossier'], "10316333")
        self.assertEqual(url_info['olo'], "3304")
        self.assertEqual(url_info['document_barcode'], "ECS0000004420_000_000")
        self.assertEqual(url_info['source_file'], False)

    def test_get_info_from_wabo_url_with_underscores_and_hyphens_in_barcode(self):
        url_info = get_info_from_iiif_url("2/wabo:SDO-10316333-3304_ECS0000004420-000_00-00/info.json", False)
        self.assertEqual(url_info['source'], "wabo")
        self.assertEqual(url_info['stadsdeel'], "SDO")
        self.assertEqual(url_info['dossier'], "10316333")
        self.assertEqual(url_info['olo'], "3304")
        self.assertEqual(url_info['document_barcode'], "ECS0000004420-000_00-00")
        self.assertEqual(url_info['source_file'], False)

    def test_get_info_from_wabo_url_wrong_formatted_url(self):
        self.assertRaises(InvalidIIIFUrlError, get_info_from_iiif_url, "2/", False)

    def test_create_wabo_url(self):
        url_info = get_info_from_iiif_url(WABO_IMG_URL, False)
        metadata = {
            'documenten': [
                {
                    'barcode': '628547',
                    'bestanden': [{"filename": "SDZ/UIT/COH/628547.PDF"}]
                }
            ]
        }

        wabo_url = create_wabo_url(metadata=metadata, url_info=url_info)
        self.assertEqual(wabo_url, '2/wabo:SDZ-UIT-COH-628547.PDF/full/1000,1000/0/default.jpg')

    def test_create_wabo_url_source_file(self):
        url_info = get_info_from_iiif_url(WABO_IMG_URL, True)
        metadata = {
            'documenten': [
                {
                    'barcode': '628547',
                    'bestanden': [{"filename": "SDZ/UIT/COH/628547.PDF"}]
                }
            ]
        }

        wabo_url = create_wabo_url(metadata=metadata, url_info=url_info)
        self.assertEqual(wabo_url, 'SDZ/UIT/COH/628547.PDF')

    def test_create_file_url_and_headers(self):
        metadata = {
            'documenten': [
                {
                    'barcode': '628547',
                    'bestanden': [{"filename": "SDZ/UIT/COH/628547.PDF"}]
                }
            ]
        }

        # pre-wabo with no headers
        url, headers, cert = create_file_url_and_headers(
            {},
            {'source': 'edepot'},
            PRE_WABO_IMG_URL,
            metadata
        )
        self.assertEqual(url, f"{settings.IIIF_BASE_URL}:{settings.IIIF_PORT}/iiif/{PRE_WABO_IMG_URL}")
        self.assertEqual(headers, {})
        self.assertEqual(cert, ())

        # pre-wabo with one header (which we expect to not be used)
        url, headers, cert = create_file_url_and_headers(
            {'HTTP_X_FORWARDED_PROTO': 'a'},
            {'source': 'edepot'},
            PRE_WABO_IMG_URL,
            metadata
        )
        self.assertEqual(url, f"{settings.IIIF_BASE_URL}:{settings.IIIF_PORT}/iiif/{PRE_WABO_IMG_URL}")
        self.assertEqual(headers, {})
        self.assertEqual(cert, ())

        # pre-wabo with one header (which we expect to not be used)
        url, headers, cert = create_file_url_and_headers(
            {'HTTP_X_FORWARDED_HOST': 'a'},
            {'source': 'edepot'},
            PRE_WABO_IMG_URL,
            metadata
        )
        self.assertEqual(url, f"{settings.IIIF_BASE_URL}:{settings.IIIF_PORT}/iiif/{PRE_WABO_IMG_URL}")
        self.assertEqual(headers, {})
        self.assertEqual(cert, ())

        # pre-wabo with both forwarded headers (which we both expect to be used)
        url, headers, cert = create_file_url_and_headers(
            {'HTTP_X_FORWARDED_PROTO': 'proto', 'HTTP_X_FORWARDED_HOST': 'host'},
            {'source': 'edepot'},
            PRE_WABO_IMG_URL,
            metadata
        )
        self.assertEqual(url, f"{settings.IIIF_BASE_URL}:{settings.IIIF_PORT}/iiif/{PRE_WABO_IMG_URL}")
        self.assertEqual(headers['X-Forwarded-Proto'], 'proto')
        self.assertEqual(headers['X-Forwarded-Host'], 'host')
        self.assertEqual(cert, ())

        # pre-wabo with other structure 1
        url, headers, cert = create_file_url_and_headers(
            {},
            {'source': 'edepot'},
            PRE_WABO_IMG_URL_X1,
            metadata
        )

        self.assertEqual(url, f"{settings.IIIF_BASE_URL}:{settings.IIIF_PORT}/iiif/{PRE_WABO_IMG_URL_X1.replace('SQ1452-','')}")

        # pre-wabo with other structure 2
        url, headers, cert = create_file_url_and_headers(
            {},
            {'source': 'edepot'},
            PRE_WABO_IMG_URL_X2,
            metadata
        )

        self.assertEqual(url,
                         f"{settings.IIIF_BASE_URL}:{settings.IIIF_PORT}/iiif/{PRE_WABO_IMG_URL_X2.replace('SQ11426-', '')}")

        # wabo with adjusted url and X-Forwarded-ID
        url, headers, cert = create_file_url_and_headers(
            {},
            {
                'source': 'wabo',
                'document_barcode': '628547',
                'formatting': 'full/1000,1000/0/default.jpg',
                'source_file': False
            },
            WABO_IMG_URL,
            metadata
        )
        self.assertEqual(url, f"{settings.IIIF_BASE_URL}:{settings.IIIF_PORT}/iiif/2/wabo:SDZ-UIT-COH-628547.PDF/full/1000,1000/0/default.jpg")
        self.assertEqual(headers['X-Forwarded-ID'], 'wabo:SDZ-38657-4900487_628547')
        self.assertEqual(cert, ())

        # wabo with adjusted url and X-Forwarded-ID and both forwarded headers
        url, headers, cert = create_file_url_and_headers(
            {'HTTP_X_FORWARDED_PROTO': 'proto', 'HTTP_X_FORWARDED_HOST': 'host'},
            {
                'source': 'wabo',
                'document_barcode': '628547',
                'formatting': 'full/1000,1000/0/default.jpg',
                'source_file': False
            },
            WABO_IMG_URL,
            metadata
        )
        self.assertEqual(url, f"{settings.IIIF_BASE_URL}:{settings.IIIF_PORT}/iiif/2/wabo:SDZ-UIT-COH-628547.PDF/full/1000,1000/0/default.jpg")
        self.assertEqual(len(headers), 3)
        self.assertEqual(headers['X-Forwarded-ID'], 'wabo:SDZ-38657-4900487_628547')
        self.assertEqual(headers['X-Forwarded-Proto'], 'proto')
        self.assertEqual(headers['X-Forwarded-Host'], 'host')
        self.assertEqual(cert, ())

        # wabo with source_file
        url, headers, cert = create_file_url_and_headers(
            {},
            {
                'source': 'wabo',
                'document_barcode': '628547',
                'formatting': 'full/1000,1000/0/default.jpg',
                'source_file': True
            },
            WABO_IMG_URL,
            metadata
        )
        self.assertEqual(url, f"{settings.WABO_BASE_URL}SDZ/UIT/COH/628547.PDF")
        self.assertEqual(cert, '/tmp/sw444v1912.pem')

    def test_get_authentication_jwt(self):
        token = create_mail_login_token('jwttest@amsterdam.nl', settings.SECRET_KEY)
        decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        self.assertEqual(len(decoded.keys()), 3)
        self.assertIn('exp', decoded.keys())
        self.assertIn('scopes', decoded.keys())
        self.assertIn('sub', decoded.keys())
        self.assertEqual(decoded['sub'], 'jwttest@amsterdam.nl')
        self.assertEqual(len(decoded['scopes']), 1)
        self.assertEqual(decoded['scopes'][0], settings.BOUWDOSSIER_READ_SCOPE)
