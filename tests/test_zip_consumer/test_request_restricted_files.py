import json
import os
import zipfile
from io import BytesIO
from unittest.mock import patch
from uuid import UUID

import pytest
from django.conf import settings
from django.core import mail

from tests.test_settings import (
    PRE_WABO_IMG_URL_DOUBLE_DOSSIER,
    PRE_WABO_IMG_URL_WITH_SCALING,
)
from tests.tools import MockResponse, create_authz_token
from zip_consumer.queue_zip_consumer import AzureZipQueueConsumer


@pytest.fixture
def restricted_meta_data_mock_response() -> MockResponse:
    return MockResponse(
        200,
        json_content={
            "access": settings.ACCESS_RESTRICTED,
            "documenten": [
                {
                    "barcode": "ST00000126",
                    "access": settings.ACCESS_RESTRICTED,
                    "bestanden": [
                        {
                            "filename": "test.jpg",
                            "file_pad": "SDC/00001/KEY2/test.jpg",
                            "url": "https://bouwdossiers.amsterdam.nl/iiif/2/wabo:SDC_1~NAA_1",
                        }
                    ],
                },
                {
                    "subdossier_titel": "Aanvraag: Public",
                    "barcode": "ST00000127",
                    "access": settings.ACCESS_PUBLIC,
                    "bestanden": [
                        {
                            "filename": "test-public.jpg",
                            "file_pad": "SDC/00001/KEY2/test.jpg",
                            "url": "https://bouwdossiers.amsterdam.nl/iiif/2/wabo:SDC_1~NAA_2",
                        }
                    ],
                },
            ],
        },
    )


@pytest.fixture
def zip_job_blob_data() -> dict:
    return {
        "email_address": "authztest@amsterdam.nl",
        "scope": "BD/X",
        "is_mail_login": "false",
        "urls": {
            "2/edepot:ST_00015~ST00000126_0/full/50,50/0/default.jpg": {
                "url_info": {
                    "source": "edepot",
                    "formatting": "full/50,50/0/default.jpg",
                    "region": "full",
                    "scaling": "50,50",
                    "info_json": "false",
                    "stadsdeel": "ST",
                    "dossier": "00015",
                    "document_barcode": "ST00000126",
                    "filenr": "0",
                }
            },
            "2/edepot:ST_00015~ST00000127_0/full/50,50/0/default.jpg": {
                "url_info": {
                    "source": "edepot",
                    "formatting": "full/50,50/0/default.jpg",
                    "region": "full",
                    "scaling": "50,50",
                    "info_json": "false",
                    "stadsdeel": "ST",
                    "dossier": "00015",
                    "document_barcode": "ST00000127",
                    "filenr": "0",
                }
            },
        },
    }


@pytest.mark.parametrize(
    "scopes,expected_status_code,messages_on_queue",
    (
        (settings.BOUWDOSSIER_PUBLIC_SCOPE, 401, 0),
        (settings.BOUWDOSSIER_READ_SCOPE, 200, 1),
        (settings.BOUWDOSSIER_EXTENDED_SCOPE, 200, 1),
        ((settings.BOUWDOSSIER_PUBLIC_SCOPE, settings.BOUWDOSSIER_READ_SCOPE), 200, 1),
        (
            (settings.BOUWDOSSIER_READ_SCOPE, settings.BOUWDOSSIER_EXTENDED_SCOPE),
            200,
            1,
        ),
    ),
)
@patch("iiif.metadata.do_metadata_request")
def test_request_restricted_images(
    mock_do_metadata_request,
    client,
    restricted_meta_data_mock_response,
    test_queue_client,
    scopes,
    expected_status_code,
    messages_on_queue,
):
    mock_do_metadata_request.return_value = restricted_meta_data_mock_response

    bearer_token = create_authz_token(scopes)
    header = {"HTTP_AUTHORIZATION": f"Bearer {bearer_token}"}

    response = client.post(
        "/iiif/zip/",
        json.dumps(
            {
                "urls": [
                    f"https://bouwdossiers.amsterdam.nl/iiif/{PRE_WABO_IMG_URL_WITH_SCALING}",
                    f"https://bouwdossiers.amsterdam.nl/iiif/{PRE_WABO_IMG_URL_DOUBLE_DOSSIER}",
                ]
            }
        ),
        content_type="application/json",
        **header,
    )

    assert response.status_code == expected_status_code

    queue_messages = list(test_queue_client.receive_messages(max_messages=2))
    assert (
        len(queue_messages) == messages_on_queue
    ), f"Expected {messages_on_queue} message(s) in the queue"


@patch("iiif.metadata.do_metadata_request")
@patch("iiif.image_server.get_file")
@patch("zip_consumer.zip_tools.uuid4")
def test_request_restricted_images_in_zip(
    mocked_uuid4,
    mocked_get_file,
    mock_do_metadata_request,
    restricted_meta_data_mock_response,
    test_image_data_factory,
    zip_jobs_blob_container,
    zip_job_blob_data,
    azure_queue_message_factory,
    download_blob_container,
    tmp_path,
):
    fixed_uuid = UUID(bytes=os.urandom(16), version=4)
    mocked_uuid4.return_value = fixed_uuid

    message_content = {
        "version": "zip_job_v1",
        "data": "zip_job_blob_data",
    }
    message = azure_queue_message_factory(content=json.dumps(message_content))
    zip_jobs_blob_container.upload_blob(
        name="zip_job_blob_data", data=json.dumps(zip_job_blob_data)
    )

    mock_do_metadata_request.return_value = restricted_meta_data_mock_response

    image_url = "2/edepot:ST_00015~ST00000126_0"
    test_image_data = test_image_data_factory("test-image-96x85.jpg")
    mocked_file_response = MockResponse(
        status_code=200, content=test_image_data, headers={"Content-Type": "image/jpg"}
    )
    mocked_get_file.return_value = mocked_file_response, image_url

    zip_queue_consumer = AzureZipQueueConsumer()
    zip_queue_consumer.process_message(message)

    assert len(mail.outbox) == 1

    email = mail.outbox[0]
    assert email.subject == "Downloadlink Bouw- en omgevingdossiers"
    assert email.from_email == "bouwdossiers@amsterdam.nl"
    assert email.to == ["authztest@amsterdam.nl"]
    assert (
        "U kunt de aangevraagde documenten downloaden gedurende 7 dagen via deze link"
        in email.body
    )
    assert (
        "http://localhost:10000/devstoreaccount1/container/blob?mock_sas_token"
        in email.body
    )

    blob_data = download_blob_container.download_blob(f"{fixed_uuid}.zip")
    zip_bytes = blob_data.readall()

    with zipfile.ZipFile(BytesIO(zip_bytes)) as zip_file:
        zip_file.extractall(tmp_path)

    report_file = tmp_path / f"{fixed_uuid}" / "report.txt"
    assert report_file.exists()

    with report_file.open("r") as f:
        lines = f.readlines()

    assert len(lines) == 3
    assert lines[0].strip() == "The following files were requested:"
    assert lines[1].strip() == "test.jpg: included"
    assert lines[2].strip() == "test-public.jpg: included"

    extracted_files = list((tmp_path / f"{fixed_uuid}").iterdir())
    assert len(extracted_files) == 3

    image_file = tmp_path / f"{fixed_uuid}" / "test.jpg"
    assert image_file.exists()

    image_file = tmp_path / f"{fixed_uuid}" / "test-public.jpg"
    assert image_file.exists()
