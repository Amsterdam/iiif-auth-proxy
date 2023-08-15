import json
import logging
from datetime import datetime, timedelta
from unittest.mock import patch

import pytz
import time_machine
from django.conf import settings
from django.test import override_settings
from requests.exceptions import ConnectTimeout

from iiif.authentication import (
    RESPONSE_CONTENT_COPYRIGHT,
    RESPONSE_CONTENT_NO_DOCUMENT_IN_METADATA,
    RESPONSE_CONTENT_NO_TOKEN,
    RESPONSE_CONTENT_RESTRICTED,
    create_mail_login_token,
)
from iiif.cantaloupe import RESPONSE_CONTENT_ERROR_RESPONSE_FROM_CANTALOUPE
from iiif.generate_token import create_authz_token
from iiif.metadata import RESPONSE_CONTENT_ERROR_RESPONSE_FROM_METADATA_SERVER
from tests.tools import MockResponse

log = logging.getLogger(__name__)
timezone = pytz.timezone("UTC")

IMAGE_BINARY_DATA = bytes(10)
PRE_WABO_IMG_URL = "2/edepot:ST-00015-ST00000126_00001.jpg/full/1000,1000/0/default.jpg"
PRE_WABO_IMG_URL_X1 = (
    "2/edepot:SQ1452-SQ-01452%20(2)-SQ10079651_00001.jpg/full/1000,1000/0/default.jpg"
)
PRE_WABO_IMG_URL_X2 = "2/edepot:SQ11426-SQ-file5BAIoi-SQ10092307_00001.jpg/info.json"
WABO_IMG_URL = "2/wabo:SDZ-38657-4900487_628547/full/1000,1000/0/default.jpg"




class TestFileRetrievalWithAuthz:
    def setup_method(self):
        self.url = "/iiif/"

    def test_get_image_with_wrongly_formatted_url(self, client):
        header = {
            "HTTP_AUTHORIZATION": "Bearer "
            + create_authz_token(
                [settings.BOUWDOSSIER_READ_SCOPE, settings.BOUWDOSSIER_EXTENDED_SCOPE]
            )
        }
        response = client.get(self.url + "wrong_formatted_image_url.jpg", **header)
        assert response.status_code == 400
        assert response.content.decode("utf-8") == "Invalid formatted url"

    @patch("iiif.cantaloupe.get_image_from_iiif_server")
    @patch("iiif.metadata.do_metadata_request")
    def test_get_image_which_does_not_exist_in_metadata(
        self, mock_do_metadata_request, mock_get_image_from_iiif_server, client
    ):
        # Setting up mocks
        mock_do_metadata_request.return_value = MockResponse(
            200,
            json_content={
                "access": settings.ACCESS_PUBLIC,
                "documenten": [],  # This is empty on purpose to test non existing documents in metadata
            },
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200, content=IMAGE_BINARY_DATA
        )

        header = {
            "HTTP_AUTHORIZATION": "Bearer "
            + create_authz_token(settings.BOUWDOSSIER_READ_SCOPE)
        }
        response = client.get(self.url + PRE_WABO_IMG_URL, **header)
        assert response.status_code == 404
        assert (
            response.content.decode("utf-8") == RESPONSE_CONTENT_NO_DOCUMENT_IN_METADATA
        )

    @patch("iiif.cantaloupe.get_image_from_iiif_server")
    @patch("iiif.metadata.do_metadata_request")
    def test_keycloak_token_is_sent_to_metadata_server(
        self, mock_do_metadata_request, mock_get_image_from_iiif_server, client
    ):
        # Setting up mocks
        mock_do_metadata_request.return_value = MockResponse(
            200,
            json_content={
                "access": settings.ACCESS_RESTRICTED,
                "documenten": [
                    {"barcode": "ST00000126", "access": settings.ACCESS_RESTRICTED}
                ],
            },
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200, content=IMAGE_BINARY_DATA, headers={}
        )

        mock_token = "Bearer " + create_authz_token(
            [settings.BOUWDOSSIER_READ_SCOPE, settings.BOUWDOSSIER_EXTENDED_SCOPE]
        )
        header = {"HTTP_AUTHORIZATION": mock_token}
        response = client.get(self.url + WABO_IMG_URL, **header)
        assert response.status_code == 505

    def test_get_image_when_metadata_server_is_not_available(self, client):
        header = {
            "HTTP_AUTHORIZATION": "Bearer "
            + create_authz_token(settings.BOUWDOSSIER_READ_SCOPE)
        }
        response = client.get(self.url + PRE_WABO_IMG_URL, **header)
        assert response.status_code == 502
        assert (
            response.content.decode("utf-8")
            == RESPONSE_CONTENT_ERROR_RESPONSE_FROM_METADATA_SERVER
        )

    @patch("iiif.metadata.do_metadata_request")
    def test_get_image_when_cantaloupe_server_is_not_available(
        self, mock_do_metadata_request, client
    ):
        # Setting up mocks
        mock_do_metadata_request.return_value = MockResponse(
            200,
            json_content={
                "access": settings.ACCESS_PUBLIC,
                "documenten": [
                    {"barcode": "ST00000126", "access": settings.ACCESS_PUBLIC}
                ],
            },
        )

        header = {
            "HTTP_AUTHORIZATION": "Bearer "
            + create_authz_token(settings.BOUWDOSSIER_READ_SCOPE)
        }
        response = client.get(self.url + PRE_WABO_IMG_URL, **header)
        assert response.status_code == 502
        assert (
            response.content.decode("utf-8")
            == RESPONSE_CONTENT_ERROR_RESPONSE_FROM_CANTALOUPE + " ConnectionError"
        )

    @patch("iiif.cantaloupe.get_image_from_iiif_server")
    @patch("iiif.metadata.do_metadata_request")
    def test_get_image_when_cantaloupe_gives_ConnectTimeout(
        self, mock_do_metadata_request, mock_get_image_from_iiif_server, client
    ):
        # Setting up mocks
        mock_do_metadata_request.return_value = MockResponse(
            200,
            json_content={
                "access": settings.ACCESS_PUBLIC,
                "documenten": [
                    {"barcode": "ST00000126", "access": settings.ACCESS_PUBLIC}
                ],
            },
        )
        mock_get_image_from_iiif_server.side_effect = ConnectTimeout()

        header = {
            "HTTP_AUTHORIZATION": "Bearer "
            + create_authz_token(settings.BOUWDOSSIER_READ_SCOPE)
        }
        response = client.get(self.url + PRE_WABO_IMG_URL, **header)
        assert response.status_code == 502
        assert (
            response.content.decode("utf-8")
            == RESPONSE_CONTENT_ERROR_RESPONSE_FROM_CANTALOUPE + " ConnectTimeout"
        )

    @patch("iiif.cantaloupe.get_image_from_iiif_server")
    @patch("iiif.metadata.do_metadata_request")
    def test_get_public_image_without_token(
        self, mock_do_metadata_request, mock_get_image_from_iiif_server, client
    ):
        # Setting up mocks
        mock_do_metadata_request.return_value = MockResponse(
            200,
            json_content={
                "access": settings.ACCESS_PUBLIC,
                "documenten": [
                    {"barcode": "ST00000126", "access": settings.ACCESS_PUBLIC}
                ],
            },
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200, content=IMAGE_BINARY_DATA
        )

        response = client.get(self.url + PRE_WABO_IMG_URL)
        assert response.status_code == 401
        assert response.content.decode("utf-8") == RESPONSE_CONTENT_NO_TOKEN

    @patch("iiif.cantaloupe.get_image_from_iiif_server")
    @patch("iiif.metadata.do_metadata_request")
    def test_get_restricted_image_without_token(
        self, mock_do_metadata_request, mock_get_image_from_iiif_server, client
    ):
        # Setting up mocks
        mock_do_metadata_request.return_value = MockResponse(
            200,
            json_content={
                "access": settings.ACCESS_RESTRICTED,
                "documenten": [
                    {"barcode": "ST00000126", "access": settings.ACCESS_RESTRICTED}
                ],
            },
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200, content=IMAGE_BINARY_DATA
        )

        response = client.get(self.url + PRE_WABO_IMG_URL)
        assert response.status_code == 401
        assert response.content.decode("utf-8") == RESPONSE_CONTENT_NO_TOKEN

    @patch("iiif.cantaloupe.get_image_from_iiif_server")
    @patch("iiif.metadata.do_metadata_request")
    def test_get_restricted_image_in_public_dossier_without_token(
        self, mock_do_metadata_request, mock_get_image_from_iiif_server, client
    ):
        # Setting up mocks
        mock_do_metadata_request.return_value = MockResponse(
            200,
            json_content={
                "access": settings.ACCESS_PUBLIC,
                "documenten": [
                    {"barcode": "ST00000126", "access": settings.ACCESS_RESTRICTED}
                ],
            },
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200, content=IMAGE_BINARY_DATA
        )

        response = client.get(self.url + PRE_WABO_IMG_URL)
        assert response.status_code == 401
        assert response.content.decode("utf-8") == RESPONSE_CONTENT_NO_TOKEN

    @patch("iiif.cantaloupe.get_image_from_iiif_server")
    @patch("iiif.metadata.do_metadata_request")
    def test_get_public_image_in_restricted_dossier_without_token(
        self, mock_do_metadata_request, mock_get_image_from_iiif_server, client
    ):
        # Setting up mocks
        mock_do_metadata_request.return_value = MockResponse(
            200,
            json_content={
                "access": settings.ACCESS_RESTRICTED,
                "documenten": [
                    {"barcode": "ST00000126", "access": settings.ACCESS_PUBLIC}
                ],
            },
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200, content=IMAGE_BINARY_DATA
        )

        response = client.get(self.url + PRE_WABO_IMG_URL)
        assert response.status_code == 401
        assert response.content.decode("utf-8") == RESPONSE_CONTENT_NO_TOKEN

    @patch("iiif.cantaloupe.get_image_from_iiif_server")
    @patch("iiif.metadata.do_metadata_request")
    def test_get_public_image_with_read_scope(
        self, mock_do_metadata_request, mock_get_image_from_iiif_server, client
    ):
        # Setting up mocks
        mock_do_metadata_request.return_value = MockResponse(
            200,
            json_content={
                "access": settings.ACCESS_PUBLIC,
                "documenten": [
                    {
                        "barcode": "ST00000126",
                        "access": settings.ACCESS_PUBLIC,
                        "copyright": settings.COPYRIGHT_YES,
                    },
                    {
                        "barcode": "SQ10079651",
                        "access": settings.ACCESS_PUBLIC,
                        "copyright": settings.COPYRIGHT_NO,
                    },
                    {"barcode": "SQ10092307", "access": settings.ACCESS_PUBLIC},
                ],
            },
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200, content=IMAGE_BINARY_DATA, headers={"Content-Type": "image/png"}
        )

        header = {
            "HTTP_AUTHORIZATION": "Bearer "
            + create_authz_token(settings.BOUWDOSSIER_READ_SCOPE)
        }
        response = client.get(self.url + PRE_WABO_IMG_URL, **header)
        assert response.status_code == 200
        assert response.content == IMAGE_BINARY_DATA

        response = client.get(self.url + PRE_WABO_IMG_URL_X1, **header)
        assert response.status_code == 200
        assert response.content == IMAGE_BINARY_DATA

        response = client.get(self.url + PRE_WABO_IMG_URL_X2, **header)
        assert response.status_code == 200
        assert response.content == IMAGE_BINARY_DATA

    @patch("iiif.cantaloupe.get_image_from_iiif_server")
    @patch("iiif.metadata.do_metadata_request")
    def test_get_restricted_image_with_read_scope(
        self, mock_do_metadata_request, mock_get_image_from_iiif_server, client
    ):
        # Setting up mocks
        mock_do_metadata_request.return_value = MockResponse(
            200,
            json_content={
                "access": settings.ACCESS_RESTRICTED,
                "documenten": [
                    {"barcode": "ST00000126", "access": settings.ACCESS_RESTRICTED}
                ],
            },
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200, content=IMAGE_BINARY_DATA, headers={"Content-Type": "image/png"}
        )

        header = {
            "HTTP_AUTHORIZATION": "Bearer "
            + create_authz_token(settings.BOUWDOSSIER_READ_SCOPE)
        }
        response = client.get(self.url + PRE_WABO_IMG_URL, **header)
        assert response.status_code == 401
        assert response.content.decode("utf-8") == RESPONSE_CONTENT_RESTRICTED

    @patch("iiif.cantaloupe.get_image_from_iiif_server")
    @patch("iiif.metadata.do_metadata_request")
    def test_get_public_image_with_extended_scope(
        self, mock_do_metadata_request, mock_get_image_from_iiif_server, client
    ):
        # Setting up mocks
        mock_do_metadata_request.return_value = MockResponse(
            200,
            json_content={
                "access": settings.ACCESS_PUBLIC,
                "documenten": [
                    {"barcode": "ST00000126", "access": settings.ACCESS_PUBLIC}
                ],
            },
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200, content=IMAGE_BINARY_DATA, headers={"Content-Type": "image/png"}
        )

        header = {
            "HTTP_AUTHORIZATION": "Bearer "
            + create_authz_token(
                [settings.BOUWDOSSIER_READ_SCOPE, settings.BOUWDOSSIER_EXTENDED_SCOPE]
            )
        }
        response = client.get(self.url + PRE_WABO_IMG_URL, **header)
        assert response.status_code == 200
        assert response.content == IMAGE_BINARY_DATA

    @patch("iiif.cantaloupe.get_image_from_iiif_server")
    @patch("iiif.metadata.do_metadata_request")
    def test_get_restricted_image_with_extended_scope(
        self, mock_do_metadata_request, mock_get_image_from_iiif_server, client
    ):
        # Setting up mocks
        mock_do_metadata_request.return_value = MockResponse(
            200,
            json_content={
                "access": settings.ACCESS_RESTRICTED,
                "documenten": [
                    {"barcode": "ST00000126", "access": settings.ACCESS_RESTRICTED}
                ],
            },
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200, content=IMAGE_BINARY_DATA, headers={"Content-Type": "image/png"}
        )

        header = {
            "HTTP_AUTHORIZATION": "Bearer "
            + create_authz_token(
                [settings.BOUWDOSSIER_READ_SCOPE, settings.BOUWDOSSIER_EXTENDED_SCOPE]
            )
        }
        response = client.get(self.url + PRE_WABO_IMG_URL, **header)
        assert response.status_code == 200
        assert response.content == IMAGE_BINARY_DATA

    @patch("iiif.cantaloupe.get_image_from_iiif_server")
    @patch("iiif.metadata.do_metadata_request")
    def test_get_public_dossier_and_restricted_image_with_extended_scope(
        self, mock_do_metadata_request, mock_get_image_from_iiif_server, client
    ):
        # Setting up mocks
        mock_do_metadata_request.return_value = MockResponse(
            200,
            json_content={
                "access": settings.ACCESS_PUBLIC,
                "documenten": [
                    {"barcode": "ST00000126", "access": settings.ACCESS_RESTRICTED}
                ],
            },
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200, content=IMAGE_BINARY_DATA, headers={"Content-Type": "image/png"}
        )

        header = {
            "HTTP_AUTHORIZATION": "Bearer "
            + create_authz_token(
                [settings.BOUWDOSSIER_READ_SCOPE, settings.BOUWDOSSIER_EXTENDED_SCOPE]
            )
        }
        response = client.get(self.url + PRE_WABO_IMG_URL, **header)
        assert response.status_code == 200
        assert response.content == IMAGE_BINARY_DATA

    @patch("iiif.cantaloupe.get_image_from_iiif_server")
    @patch("iiif.metadata.do_metadata_request")
    def test_get_public_image_with_only_extended_scope_and_no_read_scope(
        self, mock_do_metadata_request, mock_get_image_from_iiif_server, client
    ):
        # Setting up mocks
        mock_do_metadata_request.return_value = MockResponse(
            200,
            json_content={
                "access": settings.ACCESS_PUBLIC,
                "documenten": [
                    {"barcode": "ST00000126", "access": settings.ACCESS_PUBLIC}
                ],
            },
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200, content=IMAGE_BINARY_DATA, headers={"Content-Type": "image/png"}
        )

        header = {
            "HTTP_AUTHORIZATION": "Bearer "
            + create_authz_token([settings.BOUWDOSSIER_EXTENDED_SCOPE])
        }
        response = client.get(self.url + PRE_WABO_IMG_URL, **header)
        assert response.status_code == 200
        assert response.content == IMAGE_BINARY_DATA

    @patch("iiif.cantaloupe.get_image_from_iiif_server")
    @patch("iiif.metadata.do_metadata_request")
    def test_get_restricted_image_with_only_extended_scope_and_no_read_scope(
        self, mock_do_metadata_request, mock_get_image_from_iiif_server, client
    ):
        # Setting up mocks
        mock_do_metadata_request.return_value = MockResponse(
            200,
            json_content={
                "access": settings.ACCESS_RESTRICTED,
                "documenten": [
                    {"barcode": "ST00000126", "access": settings.ACCESS_RESTRICTED}
                ],
            },
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200, content=IMAGE_BINARY_DATA, headers={"Content-Type": "image/png"}
        )

        header = {
            "HTTP_AUTHORIZATION": "Bearer "
            + create_authz_token([settings.BOUWDOSSIER_EXTENDED_SCOPE])
        }
        response = client.get(self.url + PRE_WABO_IMG_URL, **header)
        assert response.status_code == 200
        assert response.content == IMAGE_BINARY_DATA


class TestFileRetrievalWithMailJWT:
    def setup_method(self):
        self.file_url = "/iiif/"
        self.login_link_url = "/iiif/login-link-to-email/"
        self.test_email_address = "jwttest@amsterdam.nl"
        self.mail_login_token = create_mail_login_token(
            self.test_email_address, settings.SECRET_KEY
        )

    @patch("iiif.mailing.send_email")
    def test_send_dataportaal_login_url_to_burger_email_address(
        self, mock_send_email, client
    ):
        mock_send_email.return_value = None  # Prevent it from sending actual emails
        payload = {
            "email": "burger@amsterdam.nl",
            "origin_url": "https://data.amsterdam.nl",
        }
        response = client.post(
            self.login_link_url, json.dumps(payload), content_type="application/json"
        )
        assert response.status_code == 200

    def test_login_url_to_burger_fails_on_other_than_post(self, client):
        response = client.get(self.login_link_url)
        assert response.status_code == 405
        response = client.put(self.login_link_url)
        assert response.status_code == 405
        response = client.delete(self.login_link_url)
        assert response.status_code == 405

    def test_request_with_invalid_json_fails(self, client):
        response = client.post(
            self.login_link_url, "invalid json", content_type="application/json"
        )
        assert response.status_code == 400

    def test_request_with_missing_email_address_field_fails(self, client):
        response = client.post(
            self.login_link_url,
            json.dumps({"something": "else"}),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_request_with_invalid_email_address_fails(self, client):
        # Missing @
        payload = {"email": "burgeramsterdam.nl"}
        response = client.post(
            self.login_link_url, json.dumps(payload), content_type="application/json"
        )
        assert response.status_code == 400

        # Missing dot
        payload = {"email": "burger@amsterdamnl"}
        response = client.post(
            self.login_link_url, json.dumps(payload), content_type="application/json"
        )
        assert response.status_code == 400

    def test_request_with_missing_origin_url_field_fails(self, client):
        payload = json.dumps({"email": "a@b.c"})
        response = client.post(
            self.login_link_url, payload, content_type="application/json"
        )
        assert response.status_code == 400

    def test_request_with_origin_url_not_in_whitelist_fails(self, client):
        payload = json.dumps(
            {"email": "a@b.c", "origin_url": "https://somethingelse.amsterdam.nl"}
        )
        response = client.post(
            self.login_link_url, payload, content_type="application/json"
        )
        assert response.status_code == 400

    @override_settings(LOGIN_ORIGIN_URL_TLD_WHITELIST=["localhost"])
    @patch("iiif.mailing.send_email")
    def test_request_with_localhost_and_port_in_origin_url_succeeds(
        self, mock_send_email, client
    ):
        mock_send_email.return_value = None  # Prevent it from sending actual emails
        payload = {
            "email": "burger@amsterdam.nl",
            "origin_url": "https://localhost:8000/something",
        }
        response = client.post(
            self.login_link_url, json.dumps(payload), content_type="application/json"
        )
        assert response.status_code == 200

    @patch("iiif.cantaloupe.get_image_from_iiif_server")
    @patch("iiif.metadata.do_metadata_request")
    def test_get_public_image_with_read_scope(
        self, mock_do_metadata_request, mock_get_image_from_iiif_server, client
    ):
        # Setting up mocks
        mock_do_metadata_request.return_value = MockResponse(
            200,
            json_content={
                "access": settings.ACCESS_PUBLIC,
                "documenten": [
                    {"barcode": "ST00000126", "access": settings.ACCESS_PUBLIC},
                    {
                        "barcode": "SQ10079651",
                        "access": settings.ACCESS_PUBLIC,
                        "copyright": settings.COPYRIGHT_YES,
                    },
                    {"barcode": "SQ10092307", "access": settings.ACCESS_PUBLIC},
                ],
            },
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200, content=IMAGE_BINARY_DATA, headers={"Content-Type": "image/png"}
        )

        response = client.get(
            self.file_url + PRE_WABO_IMG_URL + "?auth=" + self.mail_login_token
        )
        assert response.status_code == 200
        assert response.content == IMAGE_BINARY_DATA

        response = client.get(
            self.file_url + PRE_WABO_IMG_URL_X1 + "?auth=" + self.mail_login_token
        )
        assert response.status_code == 401
        assert response.content.decode("utf-8") == RESPONSE_CONTENT_COPYRIGHT

        response = client.get(
            self.file_url + PRE_WABO_IMG_URL_X2 + "?auth=" + self.mail_login_token
        )
        assert response.status_code == 200
        assert response.content == IMAGE_BINARY_DATA

    @patch("iiif.cantaloupe.get_image_from_iiif_server")
    @patch("iiif.metadata.do_metadata_request")
    def test_get_restricted_image_with_read_scope(
        self, mock_do_metadata_request, mock_get_image_from_iiif_server, client
    ):
        # Setting up mocks
        mock_do_metadata_request.return_value = MockResponse(
            200,
            json_content={
                "access": settings.ACCESS_RESTRICTED,
                "documenten": [
                    {"barcode": "ST00000126", "access": settings.ACCESS_RESTRICTED}
                ],
            },
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200, content=IMAGE_BINARY_DATA, headers={"Content-Type": "image/png"}
        )

        response = client.get(
            self.file_url + PRE_WABO_IMG_URL + "?auth=" + self.mail_login_token
        )
        assert response.status_code == 401
        assert response.content.decode("utf-8") == RESPONSE_CONTENT_RESTRICTED

    @patch("iiif.cantaloupe.get_image_from_iiif_server")
    @patch("iiif.metadata.do_metadata_request")
    def test_get_public_image_with_expired_token(
        self, mock_do_metadata_request, mock_get_image_from_iiif_server, client
    ):
        # Setting up mocks
        mock_do_metadata_request.return_value = MockResponse(
            200,
            json_content={
                "access": settings.ACCESS_PUBLIC,
                "documenten": [
                    {"barcode": "ST00000126", "access": settings.ACCESS_PUBLIC},
                    {"barcode": "SQ10079651", "access": settings.ACCESS_PUBLIC},
                    {"barcode": "SQ10092307", "access": settings.ACCESS_PUBLIC},
                ],
            },
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200, content=IMAGE_BINARY_DATA, headers={"Content-Type": "image/png"}
        )

        # Time travel to two days ago so that the jwt token will be invalid
        with time_machine.travel(datetime.now() - timedelta(days=2)):
            jwt_token = create_mail_login_token(
                self.test_email_address, settings.SECRET_KEY
            )

        response = client.get(self.file_url + PRE_WABO_IMG_URL + "?auth=" + jwt_token)
        assert response.status_code == 401

    @patch("iiif.cantaloupe.get_image_from_iiif_server")
    @patch("iiif.metadata.do_metadata_request")
    def test_get_public_image_with_invalid_token_signature(
        self, mock_do_metadata_request, mock_get_image_from_iiif_server, client
    ):
        # Setting up mocks
        mock_do_metadata_request.return_value = MockResponse(
            200,
            json_content={
                "access": settings.ACCESS_PUBLIC,
                "documenten": [
                    {"barcode": "ST00000126", "access": settings.ACCESS_PUBLIC},
                    {"barcode": "SQ10079651", "access": settings.ACCESS_PUBLIC},
                    {"barcode": "SQ10092307", "access": settings.ACCESS_PUBLIC},
                ],
            },
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200, content=IMAGE_BINARY_DATA, headers={"Content-Type": "image/png"}
        )

        mail_login_token = create_mail_login_token(
            self.test_email_address, "invalid_key"
        )
        response = client.get(
            self.file_url + PRE_WABO_IMG_URL + "?auth=" + mail_login_token
        )
        assert response.status_code == 401

    def test_get_wabo_image_with_mail_login_fails(self, client):
        response = client.get(
            self.file_url + WABO_IMG_URL + "?auth=" + self.mail_login_token
        )
        assert response.status_code == 505
