import json
import logging
import os
from unittest.mock import ANY, patch

import pytest
import pytz
from azure.core.exceptions import ResourceNotFoundError
from django.conf import settings

from auth_mail.authentication import (
    RESPONSE_CONTENT_NO_WABO_WITH_MAIL_LOGIN,
    RESPONSE_CONTENT_RESTRICTED,
    RESPONSE_CONTENT_RESTRICTED_IN_ZIP,
    create_mail_login_token,
)
from auth_mail.generate_token import create_authz_token
from tests.test_settings import (
    IMAGE_BINARY_DATA,
    PRE_WABO_IMG_URL_BASE,
    PRE_WABO_IMG_URL_DOUBLE_DOSSIER,
    PRE_WABO_IMG_URL_WITH_SCALING,
    WABO_IMG_URL,
)
from tests.test_utils_azure import create_blob_container, create_queue
from tests.tools import MockResponse
from utils.queue import get_queue_client
from utils.storage import get_blob_from_storage_account
from zip_consumer.queue_zip_consumer import AzureZipQueueConsumer
from zip_consumer.zip_tools import TMP_BOUWDOSSIER_ZIP_FOLDER

log = logging.getLogger(__name__)
timezone = pytz.timezone("UTC")


@pytest.mark.django_db
class TestZipEndpoint:
    @pytest.fixture(autouse=True)
    def setup_method(self):
        self.url = "/iiif/zip/"
        self.BASE_URL = "https://bouwdossiers.amsterdam.nl/iiif/"
        self.test_email_address = "zip@amsterdam.nl"
        self.mail_login_token = create_mail_login_token(
            self.test_email_address, settings.SECRET_KEY
        )
        self.extended_scope_token = create_authz_token(
            [settings.BOUWDOSSIER_READ_SCOPE, settings.BOUWDOSSIER_EXTENDED_SCOPE]
        )

        create_blob_container(settings.STORAGE_ACCOUNT_CONTAINER_ZIP_QUEUE_JOBS_NAME)
        create_blob_container(settings.STORAGE_ACCOUNT_CONTAINER_NAME)
        create_queue()
        self.queue_client = get_queue_client()
        # Clear the queue to start with a clean slate
        for message in self.queue_client.receive_messages(max_messages=100):
            self.queue_client.delete_message(message)

    def get_all_queue_messages(self):
        return [m for m in self.queue_client.receive_messages(max_messages=10000)]

    def get_zip_job(self, blob_name):
        _, blob = get_blob_from_storage_account(
            settings.STORAGE_ACCOUNT_CONTAINER_ZIP_QUEUE_JOBS_NAME, blob_name
        )
        return json.loads(blob)

    @patch("iiif.metadata.do_metadata_request")
    def test_get_public_image_with_jwt_token(self, mock_do_metadata_request, client):
        # Set up mock metadata response
        mock_do_metadata_request.return_value = MockResponse(
            200,
            json_content={
                "access": settings.ACCESS_PUBLIC,
                "documenten": [
                    {
                        "barcode": "ST00000126",
                        "access": settings.ACCESS_PUBLIC,
                        "bestanden": [
                            {
                                "filename": "test.doc",
                                "file_pad": "SDC/00001/KEY2/test.doc",
                                "url": "https://bouwdossiers.amsterdam.nl/iiif/2/wabo:SDC_1~NAA_1",
                            }
                        ],
                    },
                    {
                        "barcode": "SQ10079651",
                        "access": settings.ACCESS_PUBLIC,
                        "bestanden": [
                            {
                                "filename": "test1.doc",
                                "file_pad": "SDC/00001/KEY2/test1.doc",
                                "url": "https://bouwdossiers.amsterdam.nl/iiif/2/wabo:SDC_1~NAA_1",
                            }
                        ],
                    },
                    {
                        "barcode": "SQ-01452%20(2)-SQ10079651",
                        "access": settings.ACCESS_PUBLIC,
                        "bestanden": [
                            {
                                "filename": "test2.doc",
                                "file_pad": "SDC/00001/KEY2/test2.doc",
                                "url": "https://bouwdossiers.amsterdam.nl/iiif/2/edepot:SQ_01452~SQ-01452%20(2)-SQ10079651_1",
                            }
                        ],
                    },
                ],
            },
        )
        # Request two images
        response = client.post(
            self.url + "?auth=" + self.mail_login_token,
            json.dumps(
                {
                    "urls": [
                        self.BASE_URL + PRE_WABO_IMG_URL_BASE,
                        self.BASE_URL + PRE_WABO_IMG_URL_WITH_SCALING,
                        self.BASE_URL + PRE_WABO_IMG_URL_DOUBLE_DOSSIER,
                    ]
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 200
        messages = self.get_all_queue_messages()
        assert len(messages) == 1

        job_name = json.loads(messages[0].content)["data"]
        data = self.get_zip_job(job_name)
        assert data["email_address"] == "zip@amsterdam.nl"
        assert len(data["urls"]) == 3

    @patch("iiif.metadata.do_metadata_request")
    def test_get_many_public_images(self, mock_do_metadata_request, client):
        num_dossiers = 1000
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
                        self.BASE_URL + PRE_WABO_IMG_URL_BASE + f"?q={i}"
                        for i in range(0, num_dossiers)
                    ]
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 200
        messages = self.get_all_queue_messages()
        assert len(messages) == 1

        job_name = json.loads(messages[0].content)["data"]
        data = self.get_zip_job(job_name)
        assert data["email_address"] == "zip@amsterdam.nl"
        assert len(data["urls"]) == num_dossiers

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
                        self.BASE_URL + PRE_WABO_IMG_URL_BASE,
                        self.BASE_URL + PRE_WABO_IMG_URL_WITH_SCALING,
                        self.BASE_URL + PRE_WABO_IMG_URL_DOUBLE_DOSSIER,
                    ]
                }
            ),
            content_type="application/json",
            **header,
        )

        assert response.status_code == 200
        messages = self.get_all_queue_messages()
        assert len(messages) == 1

        job_name = json.loads(messages[0].content)["data"]
        data = self.get_zip_job(job_name)
        assert data["email_address"] == "authztest@amsterdam.nl"
        assert len(data["urls"]) == 3

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
                        self.BASE_URL + PRE_WABO_IMG_URL_WITH_SCALING,
                        self.BASE_URL + PRE_WABO_IMG_URL_DOUBLE_DOSSIER,
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
                        PRE_WABO_IMG_URL_WITH_SCALING,  # NO BASE URL HERE, SO IT'S MISFORMED
                        self.BASE_URL + PRE_WABO_IMG_URL_DOUBLE_DOSSIER,
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
                        self.BASE_URL + PRE_WABO_IMG_URL_WITH_SCALING,
                    ]
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 401
        assert (
            response.content.decode("utf-8") == RESPONSE_CONTENT_NO_WABO_WITH_MAIL_LOGIN
        )
        assert len(self.get_all_queue_messages()) == 0

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
                        self.BASE_URL + PRE_WABO_IMG_URL_WITH_SCALING,
                        self.BASE_URL + PRE_WABO_IMG_URL_DOUBLE_DOSSIER,
                    ]
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 200
        assert len(self.get_all_queue_messages()) == 1

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
                        self.BASE_URL + PRE_WABO_IMG_URL_WITH_SCALING,
                        self.BASE_URL + PRE_WABO_IMG_URL_DOUBLE_DOSSIER,
                    ]
                }
            ),
            content_type="application/json",
            **header,
        )

        assert response.status_code == 200
        assert len(self.get_all_queue_messages()) == 1

    @patch("zip_consumer.queue_zip_consumer.create_storage_account_temp_url")
    @patch("iiif.image_server.get_image_from_server")
    @patch("iiif.metadata.do_metadata_request")
    @patch("auth_mail.mailing.send_email")
    @patch("zip_consumer.zip_tools.cleanup_local_files")
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
        mock_do_metadata_request,
        mock_get_image_from_server,
        mock_create_storage_account_temp_url,
        scope,
        second_image_access,
        expected_line_end,
        expected_files,
        client,
    ):
        # Setting up mocks
        mock_cleanup_local_files.return_value = None
        mock_send_email.return_value = None
        mock_do_metadata_request.return_value = MockResponse(
            200,
            json_content={
                "access": settings.ACCESS_PUBLIC,
                "documenten": [
                    {
                        "barcode": "ST00000126",
                        "access": settings.ACCESS_PUBLIC,
                        "bestanden": [
                            {
                                "filename": "test.jpg",
                                "file_pad": "SDC/00001/KEY2/test.jpg",
                                "url": "https://bouwdossiers.amsterdam.nl/iiif/2/wabo:SDC_1~NAA_1",
                            }
                        ],
                    },
                    {
                        "barcode": "SQ10079651",
                        "access": second_image_access,
                        "bestanden": [
                            {
                                "filename": "test2.jpg",
                                "file_pad": "SDC/00001/KEY2/test2.jpg",
                                "url": "https://bouwdossiers.amsterdam.nl/iiif/2/wabo:SDC_1~NAA_1",
                            }
                        ],
                    },
                    {
                        "barcode": "SQ10092307",
                        "access": settings.ACCESS_RESTRICTED,
                        "bestanden": [
                            {
                                "filename": "test3.jpg",
                                "file_pad": "SDC/00001/KEY2/test3.jpg",
                                "url": "https://bouwdossiers.amsterdam.nl/iiif/2/wabo:SDC_1~NAA_1",
                            }
                        ],
                    },  # Not requested in zip
                ],
            },
        )
        mock_get_image_from_server.return_value = MockResponse(
            200, content=IMAGE_BINARY_DATA, headers={"Content-Type": "image/png"}
        )
        mock_create_storage_account_temp_url.return_value = "https://azure.com/tempurl"

        # Request some images in a zip
        header = {"HTTP_AUTHORIZATION": "Bearer " + create_authz_token([scope])}
        response = client.post(
            self.url,
            json.dumps(
                {
                    "urls": [
                        self.BASE_URL + PRE_WABO_IMG_URL_WITH_SCALING,
                        self.BASE_URL + PRE_WABO_IMG_URL_DOUBLE_DOSSIER,
                    ]
                }
            ),
            content_type="application/json",
            **header,
        )

        assert response.status_code == 200

        messages = [m for m in self.queue_client.peek_messages()]
        assert len(messages) == 1
        job_name = json.loads(messages[0].content)["data"]

        # Then run the parser
        consumer = AzureZipQueueConsumer(end_at_empty_queue=True)
        consumer.run()

        # Test whether the records that were in the queue are correctly removed
        assert len(self.get_all_queue_messages()) == 0

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

        # Check whether an email was send
        mock_send_email.method_called_with("zip@amsterdam.nl", ANY, ANY)

        # Check whether the zip job blob was removed
        with pytest.raises(ResourceNotFoundError):
            self.get_zip_job(job_name)

        # Cleanup so that other tests are not influenced
        os.system(f"rm -rf {TMP_BOUWDOSSIER_ZIP_FOLDER}*")
