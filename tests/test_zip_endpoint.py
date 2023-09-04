import json
import logging
import os
from unittest.mock import patch

import pytest
import pytz
from django.conf import settings
from ingress.models import FailedMessage, Message

from iiif.authentication import (
    RESPONSE_CONTENT_NO_WABO_WITH_MAIL_LOGIN,
    RESPONSE_CONTENT_RESTRICTED,
    RESPONSE_CONTENT_RESTRICTED_IN_ZIP,
    create_mail_login_token,
)
from iiif.generate_token import create_authz_token
from iiif.ingress_zip_consumer import ZipConsumer
from iiif.zip_tools import TMP_BOUWDOSSIER_ZIP_FOLDER
from tests.test_iiif import (
    IMAGE_BINARY_DATA,
    PRE_WABO_IMG_URL,
    PRE_WABO_IMG_URL_X1,
    WABO_IMG_URL,
    MockResponse,
)
from tests.tools import MockResponse, call_man_command

log = logging.getLogger(__name__)
timezone = pytz.timezone("UTC")



@pytest.mark.django_db
class TestZipEndpoint:
    @pytest.fixture(autouse=True)
    def setup_method(self):
        self.url = "/iiif/zip/"
        self.BASE_URL = "https://images.data.amsterdam.nl/iiif/"
        self.test_email_address = "zip@amsterdam.nl"
        self.mail_login_token = create_mail_login_token(
            self.test_email_address, settings.SECRET_KEY
        )
        self.extended_scope_token = create_authz_token(
            [settings.BOUWDOSSIER_READ_SCOPE, settings.BOUWDOSSIER_EXTENDED_SCOPE]
        )

        call_man_command("add_collection", settings.ZIP_COLLECTION_NAME)
        call_man_command("enable_consumer", settings.ZIP_COLLECTION_NAME)

    @patch("iiif.metadata.do_metadata_request")
    def test_get_public_image_with_jwt_token(self, mock_do_metadata_request, client):
        # Set up mock metadata response
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
        # Request two images
        response = client.post(
            self.url + "?auth=" + self.mail_login_token,
            json.dumps(
                {
                    "urls": [
                        self.BASE_URL + PRE_WABO_IMG_URL,
                        self.BASE_URL + PRE_WABO_IMG_URL_X1,
                    ]
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 200
        assert Message.objects.count() == 1
        message = Message.objects.first()
        data = json.loads(message.raw_data)
        assert data["email_address"] == "zip@amsterdam.nl"
        assert len(data["urls"]) == 2
        assert "request_meta" in data

    @patch("iiif.metadata.do_metadata_request")
    def test_get_public_image_with_authz_token(self, mock_do_metadata_request, client):
        # Set up mock metadata response
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

        # Request two images
        header = {
            "HTTP_AUTHORIZATION": "Bearer "
            + create_authz_token([settings.BOUWDOSSIER_READ_SCOPE])
        }
        response = client.post(
            self.url + "?auth=" + self.mail_login_token,
            json.dumps(
                {
                    "urls": [
                        self.BASE_URL + PRE_WABO_IMG_URL,
                        self.BASE_URL + PRE_WABO_IMG_URL_X1,
                    ]
                }
            ),
            content_type="application/json",
            **header,
        )

        assert response.status_code == 200
        assert Message.objects.count() == 1
        message = Message.objects.first()
        data = json.loads(message.raw_data)
        assert data["email_address"] == "authztest@amsterdam.nl"
        assert len(data["urls"]) == 2
        assert "request_meta" in data

    def test_other_methods_than_post_fail(self, client):
        response = client.get(self.url + "?auth=" + self.mail_login_token)
        assert response.status_code == 405
        response = client.put(self.url + "?auth=" + self.mail_login_token)
        assert response.status_code == 405
        response = client.delete(self.url + "?auth=" + self.mail_login_token)
        assert response.status_code == 405

    def test_request_without_auth_fails(self, client):
        response = client.post(
            self.url,
            json.dumps(
                {
                    "urls": [
                        self.BASE_URL + PRE_WABO_IMG_URL,
                        self.BASE_URL + PRE_WABO_IMG_URL_X1,
                    ]
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 401

    def test_request_with_invalid_json_fails(self, client):
        response = client.post(
            self.url + "?auth=" + self.mail_login_token,
            "invalid json",
            content_type="application/json",
        )

        assert response.status_code == 400

    def test_request_with_missing_urls_in_json_fails(self, client):
        response = client.post(
            self.url + "?auth=" + self.mail_login_token,
            json.dumps({"something": "else"}),
            content_type="application/json",
        )

        assert response.status_code == 400

    def test_request_with_invalid_urls_in_json_fails(self, client):
        response = client.post(
            self.url + "?auth=" + self.mail_login_token,
            json.dumps(
                {
                    "urls": [
                        PRE_WABO_IMG_URL,  # NO BASE URL HERE, SO IT'S MISFORMED
                        self.BASE_URL + PRE_WABO_IMG_URL_X1,
                    ]
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 400

    def test_get_wabo_image_with_mail_login_fails(self, client):
        # Request two images of which one is a WABO image
        response = client.post(
            self.url + "?auth=" + self.mail_login_token,
            json.dumps(
                {
                    "urls": [
                        self.BASE_URL + WABO_IMG_URL,
                        self.BASE_URL + PRE_WABO_IMG_URL,
                    ]
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 401
        assert (
            response.content.decode("utf-8") == RESPONSE_CONTENT_NO_WABO_WITH_MAIL_LOGIN
        )
        assert Message.objects.count() == 0

    @patch("iiif.metadata.do_metadata_request")
    def test_request_restricted_image_with_read_scope_succeeds(
        self, mock_do_metadata_request, client
    ):
        """
        It is possible to request a restricted image with a read scope, but it should fail
        when the consumer is run. This is tested in the consumer tests below.
        """

        # Set up mock metadata response
        mock_do_metadata_request.return_value = MockResponse(
            200,
            json_content={
                "access": settings.ACCESS_PUBLIC,
                "documenten": [
                    {"barcode": "ST00000126", "access": settings.ACCESS_PUBLIC},
                    {"barcode": "SQ10079651", "access": settings.ACCESS_RESTRICTED},
                    {"barcode": "SQ10092307", "access": settings.ACCESS_PUBLIC},
                ],
            },
        )

        # Request two images
        response = client.post(
            self.url + "?auth=" + self.mail_login_token,
            json.dumps(
                {
                    "urls": [
                        self.BASE_URL + PRE_WABO_IMG_URL,
                        self.BASE_URL + PRE_WABO_IMG_URL_X1,
                    ]
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 200
        assert Message.objects.count() == 1

    @patch("iiif.metadata.do_metadata_request")
    def test_get_restricted_image_with_restricted_scope_succeeds(
        self, mock_do_metadata_request, client
    ):
        """
        Because we send the link to the zip file with sendgrid, we cannot send links to
        restricted files. Since checking the metadata for all requested files gives problems
        when dealing with very large dossiers (thousands of files) we check this in the
        consumer stage. So when restricted images are requested we give back a 200 but
        fail in the conumer stage.

        Note that this should not happen in practice, since the frontend also checks whether
        restricted files are requested and informs the user that they cannot be requested.
        """

        # Set up mock metadata response
        mock_do_metadata_request.return_value = MockResponse(
            200,
            json_content={
                "access": settings.ACCESS_PUBLIC,
                "documenten": [
                    {"barcode": "ST00000126", "access": settings.ACCESS_PUBLIC},
                    {"barcode": "SQ10079651", "access": settings.ACCESS_RESTRICTED},
                    {"barcode": "SQ10092307", "access": settings.ACCESS_PUBLIC},
                ],
            },
        )

        # Request two images with extended scope
        header = {
            "HTTP_AUTHORIZATION": "Bearer "
            + create_authz_token(
                [settings.BOUWDOSSIER_READ_SCOPE, settings.BOUWDOSSIER_EXTENDED_SCOPE]
            )
        }
        response = client.post(
            self.url,
            json.dumps(
                {
                    "urls": [
                        self.BASE_URL + PRE_WABO_IMG_URL,
                        self.BASE_URL + PRE_WABO_IMG_URL_X1,
                    ]
                }
            ),
            content_type="application/json",
            **header,
        )

        assert response.status_code == 200
        assert Message.objects.count() == 1

    @patch("iiif.cantaloupe.get_image_from_iiif_server")
    @patch("iiif.metadata.do_metadata_request")
    @patch("iiif.object_store.store_object_on_object_store")
    @patch("iiif.mailing.send_email")
    @patch("iiif.zip_tools.cleanup_local_files")
    @pytest.mark.parametrize(
        "scope, second_image_access, expected_line_end, expected_files",
        [
            (
                settings.BOUWDOSSIER_READ_SCOPE,
                settings.ACCESS_RESTRICTED,
                f"Not included in this zip because {RESPONSE_CONTENT_RESTRICTED}",
                2,  # The first file and the report.txt
            ),
            (
                settings.BOUWDOSSIER_EXTENDED_SCOPE,
                settings.ACCESS_RESTRICTED,
                f"Not included in this zip because {RESPONSE_CONTENT_RESTRICTED_IN_ZIP}",
                2,  # The first file and the report.txt
            ),
            (
                settings.BOUWDOSSIER_READ_SCOPE,
                settings.ACCESS_PUBLIC,
                "included",
                3,  # Both files and the report.txt
            ),
        ],
    )
    def test_consumer(
        self,
        mock_cleanup_local_files,
        mock_send_email,
        mock_store_object_on_object_store,
        mock_do_metadata_request,
        mock_get_image_from_iiif_server,
        scope,
        second_image_access,
        expected_line_end,
        expected_files,
        client,
    ):
        # Setting up mocks
        mock_cleanup_local_files.return_value = None
        mock_send_email.return_value = None
        mock_store_object_on_object_store.return_value = None
        mock_do_metadata_request.return_value = MockResponse(
            200,
            json_content={
                "access": settings.ACCESS_PUBLIC,
                "documenten": [
                    {"barcode": "ST00000126", "access": settings.ACCESS_PUBLIC},
                    {"barcode": "SQ10079651", "access": second_image_access},
                    {
                        "barcode": "SQ10092307",
                        "access": settings.ACCESS_RESTRICTED,
                    },  # Not requested in zip
                ],
            },
        )
        mock_get_image_from_iiif_server.return_value = MockResponse(
            200, content=IMAGE_BINARY_DATA, headers={"Content-Type": "image/png"}
        )

        # Request some images in a zip
        header = {"HTTP_AUTHORIZATION": "Bearer " + create_authz_token([scope])}
        response = client.post(
            self.url,
            json.dumps(
                {
                    "urls": [
                        self.BASE_URL + PRE_WABO_IMG_URL,
                        self.BASE_URL + PRE_WABO_IMG_URL_X1,
                    ]
                }
            ),
            content_type="application/json",
            **header,
        )

        assert response.status_code == 200
        assert Message.objects.count() == 1

        # Then run the parser
        parser = ZipConsumer()
        parser.consume(end_at_empty_queue=True)

        # Test whether the records in the ingress queue are correctly set to consumed
        assert Message.objects.filter(consume_succeeded_at__isnull=False).count() == 1
        assert FailedMessage.objects.count() == 0
        for ingress in Message.objects.all():
            assert ingress.consume_started_at is not None
            assert ingress.consume_succeeded_at is not None

        # Check whether the newly created zip file exists
        tmp_contents = sorted(
            os.listdir(TMP_BOUWDOSSIER_ZIP_FOLDER)
        )  # Sorting it so the first is the folder and the second the zip
        assert len(tmp_contents) == 2
        assert os.path.isdir(os.path.join(TMP_BOUWDOSSIER_ZIP_FOLDER, tmp_contents[0]))
        assert os.path.isfile(os.path.join(TMP_BOUWDOSSIER_ZIP_FOLDER, tmp_contents[1]))
        assert tmp_contents[0] + ".zip" == tmp_contents[1]

        # Check whether the zip contains the expected number of files
        files = os.listdir(f"{TMP_BOUWDOSSIER_ZIP_FOLDER}{tmp_contents[0]}")
        assert len(files) == expected_files

        # Check whether the report.txt contains info about the missing restrictions
        with open(
            f"{TMP_BOUWDOSSIER_ZIP_FOLDER}{tmp_contents[0]}/report.txt", "r"
        ) as f:
            assert f.readlines()[-1].endswith(expected_line_end + "\n")

        # Cleanup so that other tests are not influenced
        os.system(f"rm -rf {TMP_BOUWDOSSIER_ZIP_FOLDER}*")
