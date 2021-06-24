import json
import logging
import os
import shutil
from collections import namedtuple
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
from zipfile import ZipFile

import jwt
import pytz
import time_machine
from django.conf import settings
from django.test import Client, SimpleTestCase, TestCase, override_settings
from ingress.models import FailedMessage, Message

from iiif.authentication import (RESPONSE_CONTENT_COPYRIGHT,
                                 RESPONSE_CONTENT_NO_DOCUMENT_IN_METADATA,
                                 RESPONSE_CONTENT_NO_TOKEN,
                                 RESPONSE_CONTENT_NO_WABO_WITH_MAIL_LOGIN,
                                 RESPONSE_CONTENT_RESTRICTED,
                                 RESPONSE_CONTENT_RESTRICTED_IN_ZIP,
                                 create_mail_login_token,
                                 img_is_public_copyright)
from iiif.cantaloupe import (RESPONSE_CONTENT_ERROR_RESPONSE_FROM_CANTALOUPE,
                             create_file_url_and_headers, create_wabo_url)
from iiif.generate_token import create_authz_token
from iiif.ingress_zip_consumer import ZipConsumer
from iiif.metadata import RESPONSE_CONTENT_ERROR_RESPONSE_FROM_METADATA_SERVER
from iiif.parsing import (InvalidIIIFUrlError, get_email_address,
                          get_info_from_iiif_url)
from iiif.tools import ImmediateHttpResponse
from iiif.zip_tools import create_local_zip_file
from tests.tools_for_testing import call_man_command

log = logging.getLogger(__name__)
timezone = pytz.timezone("UTC")

IMAGE_BINARY_DATA = bytes(10)
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


class FileTestCaseWithAuthz(TestCase):
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

    @patch('iiif.cantaloupe.get_image_from_iiif_server')
    @patch('iiif.metadata.do_metadata_request')
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

    @patch('iiif.metadata.do_metadata_request')
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

    @patch('iiif.cantaloupe.get_image_from_iiif_server')
    @patch('iiif.metadata.do_metadata_request')
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

    @patch('iiif.cantaloupe.get_image_from_iiif_server')
    @patch('iiif.metadata.do_metadata_request')
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

    @patch('iiif.cantaloupe.get_image_from_iiif_server')
    @patch('iiif.metadata.do_metadata_request')
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

    @patch('iiif.cantaloupe.get_image_from_iiif_server')
    @patch('iiif.metadata.do_metadata_request')
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

    @patch('iiif.cantaloupe.get_image_from_iiif_server')
    @patch('iiif.metadata.do_metadata_request')
    def test_get_public_image_with_read_scope(self, mock_get_meta_data, mock_get_image_from_iiif_server):
        # Setting up mocks
        mock_get_meta_data.return_value = MockResponse(
            200,
            json_content={
                'access': settings.ACCESS_PUBLIC,
                'documenten': [
                    {'barcode': 'ST00000126', 'access': settings.ACCESS_PUBLIC, 'copyright': settings.COPYRIGHT_YES},
                    {'barcode': 'SQ10079651', 'access': settings.ACCESS_PUBLIC, 'copyright': settings.COPYRIGHT_NO},
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
        self.assertEqual(response.content, IMAGE_BINARY_DATA)

        response = self.c.get(self.url + PRE_WABO_IMG_URL_X1, **header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, IMAGE_BINARY_DATA)

        response = self.c.get(self.url + PRE_WABO_IMG_URL_X2, **header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, IMAGE_BINARY_DATA)

    @patch('iiif.cantaloupe.get_image_from_iiif_server')
    @patch('iiif.metadata.do_metadata_request')
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
        self.assertEqual(response.content.decode("utf-8"), RESPONSE_CONTENT_RESTRICTED)

    @patch('iiif.cantaloupe.get_image_from_iiif_server')
    @patch('iiif.metadata.do_metadata_request')
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
        self.assertEqual(response.content, IMAGE_BINARY_DATA)

    @patch('iiif.cantaloupe.get_image_from_iiif_server')
    @patch('iiif.metadata.do_metadata_request')
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
        self.assertEqual(response.content, IMAGE_BINARY_DATA)

    @patch('iiif.cantaloupe.get_image_from_iiif_server')
    @patch('iiif.metadata.do_metadata_request')
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
        self.assertEqual(response.content, IMAGE_BINARY_DATA)

    @patch('iiif.cantaloupe.get_image_from_iiif_server')
    @patch('iiif.metadata.do_metadata_request')
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
        self.assertEqual(response.content, IMAGE_BINARY_DATA)

    @patch('iiif.cantaloupe.get_image_from_iiif_server')
    @patch('iiif.metadata.do_metadata_request')
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
        self.assertEqual(response.content, IMAGE_BINARY_DATA)


class FileTestCaseWithMailJWT(SimpleTestCase):
    def setUp(self):
        self.file_url = '/iiif/'
        self.login_link_url = '/iiif/login-link-to-email/'
        self.c = Client()
        self.test_email_address = 'jwttest@amsterdam.nl'
        self.mail_login_token = create_mail_login_token(self.test_email_address, settings.SECRET_KEY)

    @patch('iiif.mailing.send_email')
    def test_send_dataportaal_login_url_to_burger_email_address(self, mock_send_email):
        mock_send_email.return_value = None  # Prevent it from sending actual emails
        payload = {'email': 'burger@amsterdam.nl', 'origin_url': 'https://data.amsterdam.nl'}
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

    def test_request_with_missing_origin_url_field_fails(self):
        payload = json.dumps({'email': 'a@b.c'})
        response = self.c.post(self.login_link_url, payload, content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_request_with_origin_url_not_in_whitelist_fails(self):
        payload = json.dumps({'email': 'a@b.c', 'origin_url': 'https://somethingelse.amsterdam.nl'})
        response = self.c.post(self.login_link_url, payload, content_type="application/json")
        self.assertEqual(response.status_code, 400)

    @override_settings(LOGIN_ORIGIN_URL_TLD_WHITELIST=['localhost'])
    @patch('iiif.mailing.send_email')
    def test_request_with_localhost_and_port_in_origin_url_succeeds(self, mock_send_email):
        mock_send_email.return_value = None  # Prevent it from sending actual emails
        payload = {'email': 'burger@amsterdam.nl', 'origin_url': 'https://localhost:8000/something'}
        response = self.c.post(self.login_link_url, json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)

    @patch('iiif.cantaloupe.get_image_from_iiif_server')
    @patch('iiif.metadata.do_metadata_request')
    def test_get_public_image_with_read_scope(self, mock_get_meta_data, mock_get_image_from_iiif_server):
        # Setting up mocks
        mock_get_meta_data.return_value = MockResponse(
            200,
            json_content={
                'access': settings.ACCESS_PUBLIC,
                'documenten': [
                    {'barcode': 'ST00000126', 'access': settings.ACCESS_PUBLIC},
                    {'barcode': 'SQ10079651', 'access': settings.ACCESS_PUBLIC, 'copyright': settings.COPYRIGHT_YES},
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
        self.assertEqual(response.content, IMAGE_BINARY_DATA)

        response = self.c.get(self.file_url + PRE_WABO_IMG_URL_X1 + '?auth=' + self.mail_login_token)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.content.decode("utf-8"), RESPONSE_CONTENT_COPYRIGHT)


        response = self.c.get(self.file_url + PRE_WABO_IMG_URL_X2 + '?auth=' + self.mail_login_token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, IMAGE_BINARY_DATA)

    @patch('iiif.cantaloupe.get_image_from_iiif_server')
    @patch('iiif.metadata.do_metadata_request')
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
        self.assertEqual(response.content.decode("utf-8"), RESPONSE_CONTENT_RESTRICTED)

    @patch('iiif.cantaloupe.get_image_from_iiif_server')
    @patch('iiif.metadata.do_metadata_request')
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

    @patch('iiif.cantaloupe.get_image_from_iiif_server')
    @patch('iiif.metadata.do_metadata_request')
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

    def test_get_wabo_image_with_mail_login_fails(self):
        response = self.c.get(self.file_url + WABO_IMG_URL + '?auth=' + self.mail_login_token)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.content.decode("utf-8"), RESPONSE_CONTENT_NO_WABO_WITH_MAIL_LOGIN)


class ToolsTestCase(SimpleTestCase):
    def setUp(self):
        self.test_email_address = 'toolstest@amsterdam.nl'

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
        self.assertEqual(decoded['scopes'][0], settings.BOUWDOSSIER_PUBLIC_SCOPE)

    def test_img_is_public_copyright(self):
        metadata = {
            'access': settings.ACCESS_PUBLIC,
            'documenten': [{'barcode': 'ST00000126', 'access': settings.ACCESS_PUBLIC}]
        }
        public, has_copyright = img_is_public_copyright(metadata, 'ST00000126')
        self.assertEqual(public, True)
        self.assertEqual(has_copyright, False)

        # Although this should not happen if on bouwdossier level access is restricted
        # and on document level it is public, the result shoulb be not public
        metadata = {
            'access': settings.ACCESS_RESTRICTED,
            'documenten': [{'barcode': 'ST00000126', 'access': settings.ACCESS_PUBLIC}]
        }
        public, has_copyright = img_is_public_copyright(metadata, 'ST00000126')
        self.assertEqual(public, False)
        self.assertEqual(has_copyright, None)

        metadata = {
            'access': settings.ACCESS_PUBLIC,
            'documenten': [{'barcode': 'ST00000126', 'access': settings.ACCESS_RESTRICTED}]
        }
        public, has_copyright = img_is_public_copyright(metadata, 'ST00000126')
        self.assertEqual(public, False)
        self.assertEqual(has_copyright, None)

        metadata = {
            'access': settings.ACCESS_PUBLIC,
            'documenten': [{'barcode': 'ST00000126', 'access': settings.ACCESS_PUBLIC, 'copyright': settings.COPYRIGHT_YES}]
        }
        public, has_copyright = img_is_public_copyright(metadata, 'ST00000126')
        self.assertEqual(public, True)
        self.assertEqual(has_copyright, True)

    def test_create_local_zip_file(self):
        # First create some files
        uuid = str(uuid4())
        folder_path = f'/tmp/{uuid}/'
        os.mkdir(folder_path)
        filenames = [f'content{i}.txt' for i in range(5)]
        for filename in filenames:
            with open(f'/tmp/{uuid}/{filename}', 'w') as f:
                f.write('content')

        # Create the zip file
        create_local_zip_file(uuid, folder_path)

        # Check whether the newly created zip file exists
        self.assertTrue(Path(f'/tmp/{uuid}.zip').is_file())

        # Unzip the file
        unzip_uuid = uuid4()
        unzip_folder = f'/tmp/{unzip_uuid}/'
        os.mkdir(unzip_folder)
        with ZipFile(f'/tmp/{uuid}.zip', 'r') as zip_ref:
            zip_ref.extractall(unzip_folder)

        os.path.isdir(os.path.join(unzip_folder, uuid))
        extracted_files = sorted([file.name for file in Path(os.path.join(unzip_folder, uuid)).glob("*")])
        self.assertEqual(extracted_files, filenames)

        # Cleanup so that other tests are not influenced
        shutil.rmtree(folder_path)
        os.remove(f'/tmp/{uuid}.zip')
        shutil.rmtree(unzip_folder)

    def test_get_email_address(self):
        Request = namedtuple('Request', 'get_token_subject')
        request = Request(get_token_subject=self.test_email_address)

        # test getting the email address from the authz token
        self.assertEqual(
            get_email_address(request, {'sub': 'a@a.a', 'email': 'b@b.b'}),
            self.test_email_address
        )

        # test getting the email address from the email login link jwt token
        request = Request(get_token_subject=None)
        self.assertEqual(
            get_email_address(request, {'sub': self.test_email_address, 'email': 'b@b.b'}),
            self.test_email_address
        )

        # test getting the email address from the keycloak token
        self.assertEqual(
            get_email_address(request, {'sub': 'other str', 'email': self.test_email_address}),
            self.test_email_address
        )

        # test getting no email address from any token
        self.assertRaises(ImmediateHttpResponse, get_email_address, request, {'sub': 'other str'})


class TestZipEndpoint(TestCase):
    def setUp(self):
        self.url = '/iiif/zip/'
        self.c = Client()
        self.BASE_URL = 'https://images.data.amsterdam.nl/iiif/'
        self.test_email_address = 'zip@amsterdam.nl'
        self.mail_login_token = create_mail_login_token(self.test_email_address, settings.SECRET_KEY)
        call_man_command('add_collection', settings.ZIP_COLLECTION_NAME)
        call_man_command('enable_consumer', settings.ZIP_COLLECTION_NAME)

    @patch('iiif.metadata.do_metadata_request')
    def test_get_public_image_with_jwt_token(self, mock_get_meta_data):
        # Set up mock metadata response
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
        # Request two images
        response = self.c.post(
            self.url + '?auth=' + self.mail_login_token,
            json.dumps({
                'urls': [
                    self.BASE_URL+PRE_WABO_IMG_URL,
                    self.BASE_URL+PRE_WABO_IMG_URL_X1
                ]
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Message.objects.count(), 1)
        message = Message.objects.first()
        data = json.loads(message.raw_data)
        self.assertEqual(data['email_address'], 'zip@amsterdam.nl')
        self.assertEqual(len(data['urls']), 2)
        self.assertIn('request_meta', data)

    @patch('iiif.metadata.do_metadata_request')
    def test_get_public_image_with_authz_token(self, mock_get_meta_data):
        # Set up mock metadata response
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

        # Request two images
        header = {'HTTP_AUTHORIZATION': "Bearer " + create_authz_token([settings.BOUWDOSSIER_READ_SCOPE])}
        response = self.c.post(
            self.url + '?auth=' + self.mail_login_token,
            json.dumps({
                'urls': [
                    self.BASE_URL+PRE_WABO_IMG_URL,
                    self.BASE_URL+PRE_WABO_IMG_URL_X1
                ]
            }),
            content_type="application/json",
            ** header
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Message.objects.count(), 1)
        message = Message.objects.first()
        data = json.loads(message.raw_data)
        self.assertEqual(data['email_address'], 'authztest@amsterdam.nl')
        self.assertEqual(len(data['urls']), 2)
        self.assertIn('request_meta', data)

    def test_other_methods_than_post_fail(self):
        response = self.c.get(self.url + '?auth=' + self.mail_login_token)
        self.assertEqual(response.status_code, 405)
        response = self.c.put(self.url + '?auth=' + self.mail_login_token)
        self.assertEqual(response.status_code, 405)
        response = self.c.delete(self.url + '?auth=' + self.mail_login_token)
        self.assertEqual(response.status_code, 405)

    def test_request_without_auth_fails(self):
        response = self.c.post(
            self.url,
            json.dumps({
                'urls': [
                    self.BASE_URL+PRE_WABO_IMG_URL,
                    self.BASE_URL+PRE_WABO_IMG_URL_X1
                ]
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 401)

    def test_request_with_invalid_json_fails(self):
        response = self.c.post(
            self.url + '?auth=' + self.mail_login_token,
            "invalid json",
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)

    def test_request_with_missing_urls_in_json_fails(self):
        response = self.c.post(
            self.url + '?auth=' + self.mail_login_token,
            json.dumps({'something': 'else'}),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)

    def test_request_with_invalid_urls_in_json_fails(self):
        response = self.c.post(
            self.url + '?auth=' + self.mail_login_token,
            json.dumps({
                'urls': [
                    PRE_WABO_IMG_URL,  # NO BASE URL HERE, SO IT'S MISFORMED
                    self.BASE_URL + PRE_WABO_IMG_URL_X1
                ]
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)

    def test_get_wabo_image_with_mail_login_fails(self):
        # Request two images of which one is a WABO image
        response = self.c.post(
            self.url + '?auth=' + self.mail_login_token,
            json.dumps({
                'urls': [
                    self.BASE_URL+WABO_IMG_URL,
                    self.BASE_URL+PRE_WABO_IMG_URL
                ]
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.content.decode("utf-8"), RESPONSE_CONTENT_NO_WABO_WITH_MAIL_LOGIN)
        self.assertEqual(Message.objects.count(), 0)


    @patch('iiif.metadata.do_metadata_request')
    def test_get_restricted_image_with_read_scope_fails(self, mock_get_meta_data):
        # Set up mock metadata response
        mock_get_meta_data.return_value = MockResponse(
            200,
            json_content={
                'access': settings.ACCESS_PUBLIC,
                'documenten': [
                    {'barcode': 'ST00000126', 'access': settings.ACCESS_PUBLIC},
                    {'barcode': 'SQ10079651', 'access': settings.ACCESS_RESTRICTED},
                    {'barcode': 'SQ10092307', 'access': settings.ACCESS_PUBLIC}
                ]
            }
        )

        # Request two images
        response = self.c.post(
            self.url + '?auth=' + self.mail_login_token,
            json.dumps({
                'urls': [
                    self.BASE_URL+PRE_WABO_IMG_URL,
                    self.BASE_URL+PRE_WABO_IMG_URL_X1
                ]
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.content.decode("utf-8"), RESPONSE_CONTENT_RESTRICTED)
        self.assertEqual(Message.objects.count(), 0)

    @patch('iiif.metadata.do_metadata_request')
    def test_get_restricted_image_with_restricted_scope_fails(self, mock_get_meta_data):
        """
        Because we send the link to the zip file with sendgrid, we cannot send links to
        restricted files. For this reason we return an error upon requesting a restricted
        file in a zip, even when the user normally has access to it. Instead, the user
        has to download restricted files one by one.
        """
        # Set up mock metadata response
        mock_get_meta_data.return_value = MockResponse(
            200,
            json_content={
                'access': settings.ACCESS_PUBLIC,
                'documenten': [
                    {'barcode': 'ST00000126', 'access': settings.ACCESS_PUBLIC},
                    {'barcode': 'SQ10079651', 'access': settings.ACCESS_RESTRICTED},
                    {'barcode': 'SQ10092307', 'access': settings.ACCESS_PUBLIC}
                ]
            }
        )

        # Request two images with extended scope
        header = {'HTTP_AUTHORIZATION': "Bearer " + create_authz_token(
            [settings.BOUWDOSSIER_READ_SCOPE, settings.BOUWDOSSIER_EXTENDED_SCOPE])}
        response = self.c.post(
            self.url,
            json.dumps({
                'urls': [
                    self.BASE_URL+PRE_WABO_IMG_URL,
                    self.BASE_URL+PRE_WABO_IMG_URL_X1
                ]
            }),
            content_type="application/json",
            ** header
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content.decode("utf-8"), RESPONSE_CONTENT_RESTRICTED_IN_ZIP)
        self.assertEqual(Message.objects.count(), 0)

    @patch('iiif.cantaloupe.get_image_from_iiif_server')
    @patch('iiif.metadata.do_metadata_request')
    @patch('iiif.object_store.store_object_on_object_store')
    @patch('iiif.mailing.send_email')
    @patch('iiif.zip_tools.cleanup_local_files')
    def test_consume_ingress(
            self,
            mock_cleanup_local_files,
            mock_send_email,
            mock_store_object_on_object_store,
            mock_get_meta_data,
            mock_get_image_from_iiif_server
    ):
        # Setting up mocks
        mock_cleanup_local_files.return_value = None
        mock_send_email.return_value = None
        mock_store_object_on_object_store.return_value = None
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

        # Request some images in a zip
        response = self.c.post(
            self.url + '?auth=' + self.mail_login_token,
            json.dumps({
                'urls': [
                    self.BASE_URL + PRE_WABO_IMG_URL,
                    self.BASE_URL + PRE_WABO_IMG_URL_X1
                ]
            }),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Message.objects.count(), 1)

        # Then run the parser
        parser = ZipConsumer()
        parser.consume(end_at_empty_queue=True)

        # Test whether the records in the ingress queue are correctly set to consumed
        self.assertEqual(Message.objects.filter(consume_succeeded_at__isnull=False).count(), 1)
        self.assertEqual(FailedMessage.objects.count(), 0)
        for ingress in Message.objects.all():
            self.assertIsNotNone(ingress.consume_started_at)
            self.assertIsNotNone(ingress.consume_succeeded_at)

        # Check whether the newly created zip file exists
        tmp_contents = sorted(os.listdir('/tmp/'))  # Sorting it so the first is the folder and the second the zip
        self.assertEqual(len(tmp_contents), 2)
        self.assertTrue(os.path.isdir(os.path.join('/tmp/', tmp_contents[0])))
        self.assertTrue(os.path.isfile(os.path.join('/tmp/', tmp_contents[1])))
        self.assertEqual(tmp_contents[0]+'.zip', tmp_contents[1])

        # Cleanup so that other tests are not influenced
        shutil.rmtree(os.path.join('/tmp/', tmp_contents[0]))
        os.remove(os.path.join('/tmp/', tmp_contents[1]))
