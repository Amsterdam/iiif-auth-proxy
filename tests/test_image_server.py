import os
from unittest.mock import patch

import pytest
from django.conf import settings

from iiif import image_server, parsing
from tests.test_settings import PRE_WABO_IMG_URL_BASE
from tests.tools import MockResponse

ONE_PRE_WABO_METADATA_CONTENT = {
    "access": settings.ACCESS_PUBLIC,
    "documenten": [
        {
            "barcode": "ST00000126",
            "access": settings.ACCESS_PUBLIC,
            "copyright": settings.COPYRIGHT_YES,
            "bestanden": [
                {
                    "filename": "ST_test.doc",
                    "file_pad": "ST/15/St_Test.doc",
                    "url": "https://bouwdossiers.amsterdam.nl/iiif/2/edepot:ST_00015~ST00000126_0",
                }
            ],
        },
    ],
}


@patch("iiif.image_server.get_image_from_server")
def test_get_file_404retry(mock_get_image_from_server):

    iiif_url = PRE_WABO_IMG_URL_BASE
    url_info = parsing.get_url_info(iiif_url, source_file=True)

    metadata = ONE_PRE_WABO_METADATA_CONTENT

    mock_get_image_from_server.side_effect = [
        MockResponse(404),
        MockResponse(404),
        MockResponse(200),
    ]

    fileresponse, file_url = image_server.get_file(url_info, metadata)

    assert fileresponse.status_code == 200
    assert file_url[-17:] == "ST/15/ST_TEST.doc"

    assert mock_get_image_from_server.call_count == 3
