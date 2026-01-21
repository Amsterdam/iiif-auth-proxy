from unittest.mock import patch

import pytest
from django.conf import settings
from requests.exceptions import Timeout

from iiif import parsing
from iiif.image_server import _get_filename_variants, get_file
from main.utils import ImmediateHttpResponse
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


@pytest.mark.parametrize("variant_index", [0, 1, 2])
@patch("requests.get")
def test_timeout_on_specific_variant_then_success(mock_requests_get, variant_index):
    """Test that timeout on one variant continues to try others"""

    def side_effect(url, *args, **kwargs):
        variants = _get_filename_variants("https://example.com/ImAgE.jpg")
        if url == variants[variant_index]:
            raise Timeout(f"Timeout for {url}")
        return MockResponse(status_code=200, content=b"image_data")

    mock_requests_get.side_effect = side_effect

    url_info = PRE_WABO_IMG_URL_BASE
    url_info = parsing.get_url_info(url_info, source_file=True)

    metadata = ONE_PRE_WABO_METADATA_CONTENT

    # Should succeed by trying other variants
    response, successful_url = get_file(url_info, metadata)
    assert response.status_code == 200


@patch("requests.get")
def test_all_variants_timeout(mock_requests_get):
    """Test that all variants timing out raises error"""
    mock_requests_get.side_effect = Timeout("Connection timeout")

    url_info = PRE_WABO_IMG_URL_BASE
    url_info = parsing.get_url_info(url_info, source_file=True)

    metadata = ONE_PRE_WABO_METADATA_CONTENT

    with pytest.raises(ImmediateHttpResponse) as exc_info:
        get_file(url_info, metadata)

    assert exc_info.value.response.status_code == 502
    # Verify all 3 variants were attempted
    assert mock_requests_get.call_count == 3


@patch("requests.get")
def test_all_variants_return_404(mock_requests_get):
    """Test that all variants returning 404 raises error"""
    mock_requests_get.return_value = MockResponse(status_code=404)

    url_info = PRE_WABO_IMG_URL_BASE
    url_info = parsing.get_url_info(url_info, source_file=True)

    metadata = ONE_PRE_WABO_METADATA_CONTENT

    get_file(url_info, metadata)

    # Verify all 3 variants were attempted
    assert mock_requests_get.call_count == 3
