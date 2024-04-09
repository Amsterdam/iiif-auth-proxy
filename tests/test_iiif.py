import json
import logging
from datetime import datetime, timedelta
from unittest.mock import ANY, patch

import pytz
import time_machine
from django.conf import settings
from django.test import override_settings
from requests.exceptions import ConnectTimeout, RequestException

from iiif.authentication import (
    RESPONSE_CONTENT_COPYRIGHT,
    RESPONSE_CONTENT_NO_DOCUMENT_IN_METADATA,
    RESPONSE_CONTENT_NO_TOKEN,
    RESPONSE_CONTENT_NO_WABO_WITH_MAIL_LOGIN,
    RESPONSE_CONTENT_RESTRICTED,
    create_mail_login_token,
)
from iiif.generate_token import create_authz_token
from iiif.image_server import RESPONSE_CONTENT_ERROR_RESPONSE_FROM_IMAGE_SERVER
from iiif.metadata import RESPONSE_CONTENT_ERROR_RESPONSE_FROM_METADATA_SERVER
from tests.tools import MockResponse

log = logging.getLogger(__name__)
timezone = pytz.timezone("UTC")


def filename_from_url(url):
    return url.split(":")[1].split("/")[0].replace("-", "/")


PRE_WABO_IMG_URL_BASE = "2/edepot:ST-00015-ST00000126_00001.jpg/"

PRE_WABO_INFO_JSON_URL = PRE_WABO_IMG_URL_BASE + "info.json"

PRE_WABO_IMG_URL_WITH_SCALING = PRE_WABO_IMG_URL_BASE + "full/50,50/0/default.jpg"
PRE_WABO_IMG_URL_WITH_EMPTY_SCALING = PRE_WABO_IMG_URL_BASE + "full//0/default.jpg"
PRE_WABO_FILE_NAME_WITH_SCALING = filename_from_url(PRE_WABO_IMG_URL_WITH_SCALING)

PRE_WABO_IMG_URL_WITH_REGION = PRE_WABO_IMG_URL_BASE + "24,24,48,48/full/0/default.jpg"
PRE_WABO_IMG_URL_WITH_REGION_NON_OVERLAPPING = (
    PRE_WABO_IMG_URL_BASE + "10000,10000,48,48/full/0/default.jpg"
)

PRE_WABO_IMG_URL_NO_SCALING = (
    "2/edepot:ST-00015-ST00000126_00001.jpg/full/full/0/default.jpg"
)
PRE_WABO_FILE_NAME_NO_SCALING = filename_from_url(PRE_WABO_IMG_URL_NO_SCALING)

PRE_WABO_IMG_URL_WITH_EXTRA_REFERENCE = (
    "2/edepot:SQ1452-SQ-01452%20(2)-SQ10079651_00001.jpg/full/full/0/default.jpg"
)
PRE_WABO_IMG_FILE_NAME_WITH_EXTRA_REFERENCE = filename_from_url(
    PRE_WABO_IMG_URL_WITH_EXTRA_REFERENCE
)

WABO_IMG_URL = "2/wabo:SDZ-38657-4900487_628547/full/1000,900/0/default.jpg"

with open("test-images/test-image-96x85.jpg", "rb") as file:
    IMAGE_BINARY_DATA = file.read()
with open("test-images/test-image-50x44.jpg", "rb") as file:
    IMAGE_BINARY_DATA_50x44 = file.read()
with open("test-images/test-image-cropped-24x24x72x72.jpg", "rb") as file:
    IMAGE_BINARY_DATA_24x24x72x72 = file.read()


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

    @patch("iiif.image_server.get_image_from_server")
    @patch("iiif.metadata.do_metadata_request")
    def test_get_image_which_does_not_exist_in_metadata(
        self, mock_do_metadata_request, mock_get_image_from_server, client
    ):
        mock_do_metadata_request.return_value = MockResponse(
            200,
            json_content={
                "access": settings.ACCESS_PUBLIC,
                "documenten": [],  # This is empty on purpose to test non existing documents in metadata
            },
        )
        mock_get_image_from_server.return_value = MockResponse(
            200, content=IMAGE_BINARY_DATA
        )

        header = {
            "HTTP_AUTHORIZATION": "Bearer "
            + create_authz_token(settings.BOUWDOSSIER_READ_SCOPE)
        }
        response = client.get(self.url + PRE_WABO_IMG_URL_WITH_SCALING, **header)
        assert response.status_code == 404
        assert (
            response.content.decode("utf-8") == RESPONSE_CONTENT_NO_DOCUMENT_IN_METADATA
        )

    def test_get_image_when_metadata_server_is_not_available(self, client):
        header = {
            "HTTP_AUTHORIZATION": "Bearer "
            + create_authz_token(settings.BOUWDOSSIER_READ_SCOPE)
        }
        response = client.get(self.url + PRE_WABO_IMG_URL_WITH_SCALING, **header)
        assert response.status_code == 502
        assert (
            response.content.decode("utf-8")
            == RESPONSE_CONTENT_ERROR_RESPONSE_FROM_METADATA_SERVER
        )

    @patch("iiif.image_server.get_image_from_server")
    @patch("iiif.metadata.do_metadata_request")
    def test_get_image_when_image_server_is_not_available(
        self, mock_do_metadata_request, mock_get_image_from_server, client
    ):
        mock_do_metadata_request.return_value = MockResponse(
            200,
            json_content={
                "access": settings.ACCESS_PUBLIC,
                "documenten": [
                    {"barcode": "ST00000126", "access": settings.ACCESS_PUBLIC}
                ],
            },
        )
        mock_get_image_from_server.side_effect = RequestException()

        header = {
            "HTTP_AUTHORIZATION": "Bearer "
            + create_authz_token(settings.BOUWDOSSIER_READ_SCOPE)
        }
        response = client.get(self.url + PRE_WABO_IMG_URL_WITH_SCALING, **header)
        assert response.status_code == 502
        assert (
            response.content.decode("utf-8")
            == RESPONSE_CONTENT_ERROR_RESPONSE_FROM_IMAGE_SERVER + " RequestException"
        )

    @patch("iiif.image_server.get_image_from_server")
    @patch("iiif.metadata.do_metadata_request")
    def test_get_image_when_image_server_gives_ConnectTimeout(
        self, mock_do_metadata_request, mock_get_image_from_server, client
    ):
        mock_do_metadata_request.return_value = MockResponse(
            200,
            json_content={
                "access": settings.ACCESS_PUBLIC,
                "documenten": [
                    {"barcode": "ST00000126", "access": settings.ACCESS_PUBLIC}
                ],
            },
        )
        mock_get_image_from_server.side_effect = ConnectTimeout()

        header = {
            "HTTP_AUTHORIZATION": "Bearer "
            + create_authz_token(settings.BOUWDOSSIER_READ_SCOPE)
        }
        response = client.get(self.url + PRE_WABO_IMG_URL_WITH_SCALING, **header)
        assert response.status_code == 502
        assert (
            response.content.decode("utf-8")
            == RESPONSE_CONTENT_ERROR_RESPONSE_FROM_IMAGE_SERVER + " ConnectTimeout"
        )

    @patch("iiif.image_server.get_image_from_server")
    @patch("iiif.metadata.do_metadata_request")
    def test_get_info_json(
        self, mock_do_metadata_request, mock_get_image_from_server, client
    ):
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
        mock_get_image_from_server.return_value = MockResponse(
            200, content=IMAGE_BINARY_DATA, headers={"Content-Type": "image/jpeg"}
        )

        header = {
            "HTTP_AUTHORIZATION": "Bearer "
            + create_authz_token(settings.BOUWDOSSIER_READ_SCOPE)
        }

        response = client.get(self.url + PRE_WABO_INFO_JSON_URL, **header)
        assert response.status_code == 200
        assert response.headers["Content-Type"] == "application/json"

        response_dict = json.loads(response.content)
        assert response_dict["width"] == 96
        assert response_dict["height"] == 85
        assert response_dict["sizes"] == [{"width": 96, "height": 85}]
        assert response_dict["profile"][1]["formats"] == ["jpg"]

    @patch("iiif.image_server.get_image_from_server")
    @patch("iiif.metadata.do_metadata_request")
    def test_get_public_image_without_token(
        self, mock_do_metadata_request, mock_get_image_from_server, client
    ):
        mock_do_metadata_request.return_value = MockResponse(
            200,
            json_content={
                "access": settings.ACCESS_PUBLIC,
                "documenten": [
                    {"barcode": "ST00000126", "access": settings.ACCESS_PUBLIC}
                ],
            },
        )
        mock_get_image_from_server.return_value = MockResponse(
            200, content=IMAGE_BINARY_DATA
        )

        response = client.get(self.url + PRE_WABO_IMG_URL_WITH_SCALING)
        assert response.status_code == 401
        assert response.content.decode("utf-8") == RESPONSE_CONTENT_NO_TOKEN

    @patch("iiif.image_server.get_image_from_server")
    @patch("iiif.metadata.do_metadata_request")
    def test_get_restricted_image_without_token(
        self, mock_do_metadata_request, mock_get_image_from_server, client
    ):
        mock_do_metadata_request.return_value = MockResponse(
            200,
            json_content={
                "access": settings.ACCESS_RESTRICTED,
                "documenten": [
                    {"barcode": "ST00000126", "access": settings.ACCESS_RESTRICTED}
                ],
            },
        )
        mock_get_image_from_server.return_value = MockResponse(
            200, content=IMAGE_BINARY_DATA
        )

        response = client.get(self.url + PRE_WABO_IMG_URL_WITH_SCALING)
        assert response.status_code == 401
        assert response.content.decode("utf-8") == RESPONSE_CONTENT_NO_TOKEN

    @patch("iiif.image_server.get_image_from_server")
    @patch("iiif.metadata.do_metadata_request")
    def test_get_restricted_image_in_public_dossier_without_token(
        self, mock_do_metadata_request, mock_get_image_from_server, client
    ):
        mock_do_metadata_request.return_value = MockResponse(
            200,
            json_content={
                "access": settings.ACCESS_PUBLIC,
                "documenten": [
                    {"barcode": "ST00000126", "access": settings.ACCESS_RESTRICTED}
                ],
            },
        )
        mock_get_image_from_server.return_value = MockResponse(
            200, content=IMAGE_BINARY_DATA
        )

        response = client.get(self.url + PRE_WABO_IMG_URL_WITH_SCALING)
        assert response.status_code == 401
        assert response.content.decode("utf-8") == RESPONSE_CONTENT_NO_TOKEN

    @patch("iiif.image_server.get_image_from_server")
    @patch("iiif.metadata.do_metadata_request")
    def test_get_public_image_in_restricted_dossier_without_token(
        self, mock_do_metadata_request, mock_get_image_from_server, client
    ):
        mock_do_metadata_request.return_value = MockResponse(
            200,
            json_content={
                "access": settings.ACCESS_RESTRICTED,
                "documenten": [
                    {"barcode": "ST00000126", "access": settings.ACCESS_PUBLIC}
                ],
            },
        )
        mock_get_image_from_server.return_value = MockResponse(
            200, content=IMAGE_BINARY_DATA
        )

        response = client.get(self.url + PRE_WABO_IMG_URL_WITH_SCALING)
        assert response.status_code == 401
        assert response.content.decode("utf-8") == RESPONSE_CONTENT_NO_TOKEN

    @patch("iiif.image_server.get_image_from_server")
    @patch("iiif.metadata.do_metadata_request")
    def test_get_public_image_with_read_scope(
        self, mock_do_metadata_request, mock_get_image_from_server, client
    ):
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
        mock_get_image_from_server.return_value = MockResponse(
            200, content=IMAGE_BINARY_DATA, headers={"Content-Type": "image/jpeg"}
        )

        header = {
            "HTTP_AUTHORIZATION": "Bearer "
            + create_authz_token(settings.BOUWDOSSIER_READ_SCOPE)
        }

        response = client.get(self.url + PRE_WABO_IMG_URL_NO_SCALING, **header)
        assert response.status_code == 200
        assert response.content == IMAGE_BINARY_DATA

        response = client.get(
            self.url + PRE_WABO_IMG_URL_WITH_EXTRA_REFERENCE, **header
        )
        assert response.status_code == 200
        assert response.content == IMAGE_BINARY_DATA

    @patch("iiif.image_server.get_image_from_server")
    @patch("iiif.metadata.do_metadata_request")
    def test_get_restricted_image_with_read_scope(
        self, mock_do_metadata_request, mock_get_image_from_server, client
    ):
        mock_do_metadata_request.return_value = MockResponse(
            200,
            json_content={
                "access": settings.ACCESS_RESTRICTED,
                "documenten": [
                    {"barcode": "ST00000126", "access": settings.ACCESS_RESTRICTED}
                ],
            },
        )
        mock_get_image_from_server.return_value = MockResponse(
            200, content=IMAGE_BINARY_DATA, headers={"Content-Type": "image/jpeg"}
        )

        header = {
            "HTTP_AUTHORIZATION": "Bearer "
            + create_authz_token(settings.BOUWDOSSIER_READ_SCOPE)
        }
        response = client.get(self.url + PRE_WABO_IMG_URL_WITH_SCALING, **header)
        assert response.status_code == 401
        assert response.content.decode("utf-8") == RESPONSE_CONTENT_RESTRICTED

    @patch("iiif.image_server.get_image_from_server")
    @patch("iiif.metadata.do_metadata_request")
    def test_get_public_image_with_extended_scope(
        self, mock_do_metadata_request, mock_get_image_from_server, client
    ):
        mock_do_metadata_request.return_value = MockResponse(
            200,
            json_content={
                "access": settings.ACCESS_PUBLIC,
                "documenten": [
                    {"barcode": "ST00000126", "access": settings.ACCESS_PUBLIC}
                ],
            },
        )
        mock_get_image_from_server.return_value = MockResponse(
            200, content=IMAGE_BINARY_DATA, headers={"Content-Type": "image/jpeg"}
        )

        header = {
            "HTTP_AUTHORIZATION": "Bearer "
            + create_authz_token(
                [settings.BOUWDOSSIER_READ_SCOPE, settings.BOUWDOSSIER_EXTENDED_SCOPE]
            )
        }
        response = client.get(self.url + PRE_WABO_IMG_URL_NO_SCALING, **header)
        assert response.status_code == 200
        assert response.content == IMAGE_BINARY_DATA

    @patch("iiif.image_server.get_image_from_server")
    @patch("iiif.metadata.do_metadata_request")
    def test_get_restricted_image_with_extended_scope(
        self, mock_do_metadata_request, mock_get_image_from_server, client
    ):
        mock_do_metadata_request.return_value = MockResponse(
            200,
            json_content={
                "access": settings.ACCESS_RESTRICTED,
                "documenten": [
                    {"barcode": "ST00000126", "access": settings.ACCESS_RESTRICTED}
                ],
            },
        )
        mock_get_image_from_server.return_value = MockResponse(
            200, content=IMAGE_BINARY_DATA, headers={"Content-Type": "image/jpeg"}
        )

        header = {
            "HTTP_AUTHORIZATION": "Bearer "
            + create_authz_token(
                [settings.BOUWDOSSIER_READ_SCOPE, settings.BOUWDOSSIER_EXTENDED_SCOPE]
            )
        }
        response = client.get(self.url + PRE_WABO_IMG_URL_NO_SCALING, **header)
        assert response.status_code == 200
        assert response.content == IMAGE_BINARY_DATA

    @patch("iiif.image_server.get_image_from_server")
    @patch("iiif.metadata.do_metadata_request")
    def test_get_public_dossier_and_restricted_image_with_extended_scope(
        self, mock_do_metadata_request, mock_get_image_from_server, client
    ):
        mock_do_metadata_request.return_value = MockResponse(
            200,
            json_content={
                "access": settings.ACCESS_PUBLIC,
                "documenten": [
                    {"barcode": "ST00000126", "access": settings.ACCESS_RESTRICTED}
                ],
            },
        )
        mock_get_image_from_server.return_value = MockResponse(
            200, content=IMAGE_BINARY_DATA, headers={"Content-Type": "image/jpeg"}
        )

        header = {
            "HTTP_AUTHORIZATION": "Bearer "
            + create_authz_token(
                [settings.BOUWDOSSIER_READ_SCOPE, settings.BOUWDOSSIER_EXTENDED_SCOPE]
            )
        }
        response = client.get(self.url + PRE_WABO_IMG_URL_NO_SCALING, **header)
        assert response.status_code == 200
        assert response.content == IMAGE_BINARY_DATA

    @patch("iiif.image_server.get_image_from_server")
    @patch("iiif.metadata.do_metadata_request")
    def test_get_public_image_with_only_extended_scope_and_no_read_scope(
        self, mock_do_metadata_request, mock_get_image_from_server, client
    ):
        mock_do_metadata_request.return_value = MockResponse(
            200,
            json_content={
                "access": settings.ACCESS_PUBLIC,
                "documenten": [
                    {"barcode": "ST00000126", "access": settings.ACCESS_PUBLIC}
                ],
            },
        )
        mock_get_image_from_server.return_value = MockResponse(
            200, content=IMAGE_BINARY_DATA, headers={"Content-Type": "image/jpeg"}
        )

        header = {
            "HTTP_AUTHORIZATION": "Bearer "
            + create_authz_token([settings.BOUWDOSSIER_EXTENDED_SCOPE])
        }
        response = client.get(self.url + PRE_WABO_IMG_URL_NO_SCALING, **header)
        assert response.status_code == 200
        assert response.content == IMAGE_BINARY_DATA

    @patch("iiif.image_server.get_image_from_server")
    @patch("iiif.metadata.do_metadata_request")
    def test_get_restricted_image_with_only_extended_scope_and_no_read_scope(
        self, mock_do_metadata_request, mock_get_image_from_server, client
    ):
        mock_do_metadata_request.return_value = MockResponse(
            200,
            json_content={
                "access": settings.ACCESS_RESTRICTED,
                "documenten": [
                    {"barcode": "ST00000126", "access": settings.ACCESS_RESTRICTED}
                ],
            },
        )
        mock_get_image_from_server.return_value = MockResponse(
            200, content=IMAGE_BINARY_DATA, headers={"Content-Type": "image/jpeg"}
        )

        header = {
            "HTTP_AUTHORIZATION": "Bearer "
            + create_authz_token([settings.BOUWDOSSIER_EXTENDED_SCOPE])
        }
        response = client.get(self.url + PRE_WABO_IMG_URL_NO_SCALING, **header)
        assert response.status_code == 200
        assert response.content == IMAGE_BINARY_DATA

    @patch("iiif.image_server.get_image_from_server")
    @patch("iiif.metadata.do_metadata_request")
    def test_get_resized_image(
        self, mock_do_metadata_request, mock_get_image_from_server, client
    ):
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
        mock_get_image_from_server.return_value = MockResponse(
            200, content=IMAGE_BINARY_DATA, headers={"Content-Type": "image/jpeg"}
        )

        header = {
            "HTTP_AUTHORIZATION": "Bearer "
            + create_authz_token(settings.BOUWDOSSIER_READ_SCOPE)
        }

        response = client.get(self.url + PRE_WABO_IMG_URL_WITH_SCALING, **header)
        assert response.status_code == 200
        assert response.content == IMAGE_BINARY_DATA_50x44

    @patch("iiif.image_server.get_image_from_server")
    @patch("iiif.metadata.do_metadata_request")
    def test_get_resized_image_without_scaling_param_raises(
        self, mock_do_metadata_request, mock_get_image_from_server, client
    ):
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
        mock_get_image_from_server.return_value = MockResponse(
            200, content=IMAGE_BINARY_DATA, headers={"Content-Type": "image/jpeg"}
        )

        header = {
            "HTTP_AUTHORIZATION": "Bearer "
            + create_authz_token(settings.BOUWDOSSIER_READ_SCOPE)
        }

        response = client.get(self.url + PRE_WABO_IMG_URL_WITH_EMPTY_SCALING, **header)
        assert response.status_code == 400

    @patch("iiif.image_server.get_image_from_server")
    @patch("iiif.metadata.do_metadata_request")
    def test_get_cropped_image(
        self, mock_do_metadata_request, mock_get_image_from_server, client
    ):
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
        mock_get_image_from_server.return_value = MockResponse(
            200, content=IMAGE_BINARY_DATA, headers={"Content-Type": "image/jpeg"}
        )

        header = {
            "HTTP_AUTHORIZATION": "Bearer "
            + create_authz_token(settings.BOUWDOSSIER_READ_SCOPE)
        }

        response = client.get(self.url + PRE_WABO_IMG_URL_WITH_REGION, **header)
        assert response.status_code == 200
        assert response.content == IMAGE_BINARY_DATA_24x24x72x72

    @patch("iiif.image_server.get_image_from_server")
    @patch("iiif.metadata.do_metadata_request")
    def test_get_cropped_image_outside_image_region_returns_400(
        self, mock_do_metadata_request, mock_get_image_from_server, client
    ):
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
        mock_get_image_from_server.return_value = MockResponse(
            200, content=IMAGE_BINARY_DATA, headers={"Content-Type": "image/jpeg"}
        )

        header = {
            "HTTP_AUTHORIZATION": "Bearer "
            + create_authz_token(settings.BOUWDOSSIER_READ_SCOPE)
        }

        response = client.get(
            self.url + PRE_WABO_IMG_URL_WITH_REGION_NON_OVERLAPPING, **header
        )
        assert response.status_code == 400


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

    @patch("iiif.image_server.get_image_from_server")
    @patch("iiif.metadata.do_metadata_request")
    def test_get_public_image_with_read_scope(
        self, mock_do_metadata_request, mock_get_image_from_server, client
    ):
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
        mock_get_image_from_server.return_value = MockResponse(
            200, content=IMAGE_BINARY_DATA, headers={"Content-Type": "image/jpeg"}
        )

        response = client.get(
            self.file_url
            + PRE_WABO_IMG_URL_NO_SCALING
            + "?auth="
            + self.mail_login_token
        )
        assert response.status_code == 200
        assert response.content == IMAGE_BINARY_DATA

        response = client.get(
            self.file_url
            + PRE_WABO_IMG_URL_WITH_EXTRA_REFERENCE
            + "?auth="
            + self.mail_login_token
        )
        assert response.status_code == 401
        assert response.content.decode("utf-8") == RESPONSE_CONTENT_COPYRIGHT

    @patch("iiif.image_server.get_image_from_server")
    @patch("iiif.metadata.do_metadata_request")
    def test_get_restricted_image_with_read_scope(
        self, mock_do_metadata_request, mock_get_image_from_server, client
    ):
        mock_do_metadata_request.return_value = MockResponse(
            200,
            json_content={
                "access": settings.ACCESS_RESTRICTED,
                "documenten": [
                    {"barcode": "ST00000126", "access": settings.ACCESS_RESTRICTED}
                ],
            },
        )
        mock_get_image_from_server.return_value = MockResponse(
            200, content=IMAGE_BINARY_DATA, headers={"Content-Type": "image/jpeg"}
        )

        response = client.get(
            self.file_url
            + PRE_WABO_IMG_URL_WITH_SCALING
            + "?auth="
            + self.mail_login_token
        )
        assert response.status_code == 401
        assert response.content.decode("utf-8") == RESPONSE_CONTENT_RESTRICTED

    @patch("iiif.image_server.get_image_from_server")
    @patch("iiif.metadata.do_metadata_request")
    def test_get_public_image_with_expired_token(
        self, mock_do_metadata_request, mock_get_image_from_server, client
    ):
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
        mock_get_image_from_server.return_value = MockResponse(
            200, content=IMAGE_BINARY_DATA, headers={"Content-Type": "image/jpeg"}
        )

        # Time travel to two days ago so that the jwt token will be invalid
        with time_machine.travel(datetime.now() - timedelta(days=2)):
            jwt_token = create_mail_login_token(
                self.test_email_address, settings.SECRET_KEY
            )

        response = client.get(
            self.file_url + PRE_WABO_IMG_URL_WITH_SCALING + "?auth=" + jwt_token
        )
        assert response.status_code == 401

    @patch("iiif.image_server.get_image_from_server")
    @patch("iiif.metadata.do_metadata_request")
    def test_get_public_image_with_invalid_token_signature(
        self, mock_do_metadata_request, mock_get_image_from_server, client
    ):
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
        mock_get_image_from_server.return_value = MockResponse(
            200, content=IMAGE_BINARY_DATA, headers={"Content-Type": "image/jpeg"}
        )

        mail_login_token = create_mail_login_token(
            self.test_email_address, "invalid_key"
        )
        response = client.get(
            self.file_url + PRE_WABO_IMG_URL_WITH_SCALING + "?auth=" + mail_login_token
        )
        assert response.status_code == 401

    def test_get_wabo_image_with_mail_login_fails(self, client):
        response = client.get(
            self.file_url + WABO_IMG_URL + "?auth=" + self.mail_login_token
        )
        assert response.status_code == 401
        assert (
            response.content.decode("utf-8") == RESPONSE_CONTENT_NO_WABO_WITH_MAIL_LOGIN
        )
