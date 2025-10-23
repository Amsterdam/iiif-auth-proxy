import os
from unittest.mock import patch

import pytest
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

CURRENT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
with open(
    os.path.join(CURRENT_DIRECTORY, "test-images/test-image-96x85.jpg"), "rb"
) as file:
    IMAGE_BINARY_DATA = file.read()


@pytest.mark.parametrize("error_mock", [404, 880])
@patch("iiif.image_server.get_image_from_server")
def test_get_image_fails(mock_get_image_from_server, error_mock):

    mock_get_image_from_server.return_value = MockResponse(error_mock)
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

    assert info_txt_contents[:30] == "SJ10027690_00001.jpg: Not incl"


@patch("iiif.image_server.get_image_from_server")
def test_get_image_200(mock_get_image_from_server):

    mock_get_image_from_server.return_value = MockResponse(
        200, content=IMAGE_BINARY_DATA, headers={"Content-Type": "image/png"}
    )
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
