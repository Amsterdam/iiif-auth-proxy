from unittest.mock import Mock, patch

import pytest
import requests
from django.conf import settings

from iiif import image_server
from tests.tools import MockResponse

METADATA_CONTENT = {
    "dossiernr": "02576",
    "stadsdeel": "SJ",
    "access": settings.ACCESS_PUBLIC,
    "documenten": [
        {
            "barcode": "SJ10027690",
            "access": settings.ACCESS_PUBLIC,
            "copyright": settings.COPYRIGHT_YES,
            "bestanden": [
                {
                    "filename": "SJ10027690_00001.jpg",
                    "file_pad": "SJ/02576/SJ10027690_00001.jpg",
                    "url": "https://bouwdossiers.amsterdam.nl/iiif/2/edepot:SJ_02576~SJ10027690_0",
                }
            ],
        },
    ],
}


@pytest.mark.parametrize("http_status_code", [404, 880])
@patch("requests.get")
def test_get_image_fails(mock_requests_get, http_status_code):
    mock_response = Mock()
    mock_response.status_code = http_status_code
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError()

    mock_requests_get.return_value = mock_response

    tmp_folder_path = "/tmp/bouwdossier-zips/"
    info_txt_contents = ""

    iiif_url = "2/edepot:SJ_02576~SJ10027690_0"
    image_info = {
        "url_info": {
            "source": "edepot",
            "formatting": "",
            "region": "null",
            "scaling": "null",
            "info_json": "false",
            "stadsdeel": "SJ",
            "dossier": "02576",
            "document_barcode": "SJ10027690",
            "filenr": "0",
        }
    }

    fail_reason = None
    metadata = METADATA_CONTENT

    info_txt_contents = image_server.download_file_for_zip(
        iiif_url,
        info_txt_contents,
        image_info["url_info"],
        fail_reason,
        metadata,
        tmp_folder_path,
    )

    assert info_txt_contents[:30] == "SJ10027690_00001.jpg: excluded"


@patch("requests.get")
def test_get_image_200(mock_requests_get, test_image_data_factory):
    test_image_data = test_image_data_factory("test-image-96x85.jpg")

    mock_requests_get.return_value = MockResponse(200, content=test_image_data, headers={"Content-Type": "image/png"})
    tmp_folder_path = "/tmp/bouwdossier-zips/"
    info_txt_contents = ""

    iiif_url = "2/edepot:SJ_02576~SJ10027690_0"
    image_info = {
        "url_info": {
            "source": "edepot",
            "formatting": "",
            "region": "null",
            "scaling": "null",
            "info_json": "false",
            "stadsdeel": "SJ",
            "dossier": "02576",
            "document_barcode": "SJ10027690",
            "filenr": "0",
        }
    }

    fail_reason = None
    metadata = METADATA_CONTENT

    info_txt_contents = image_server.download_file_for_zip(
        iiif_url,
        info_txt_contents,
        image_info["url_info"],
        fail_reason,
        metadata,
        tmp_folder_path,
    )

    assert info_txt_contents[:30] == "SJ10027690_00001.jpg: included"
