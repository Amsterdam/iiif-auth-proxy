import pytest
from django.conf import settings

from core.auth.constants import RESPONSE_CONTENT_RESTRICTED_IN_ZIP
from core.auth.document_access import check_restricted_file
from main.utils import ImmediateHttpResponse


def test_check_restricted_file_allows_public_document():
    """Test that public documents don't raise an error."""
    metadata = {
        "access": settings.ACCESS_PUBLIC,
        "documenten": [
            {"barcode": "ST00001", "access": settings.ACCESS_PUBLIC},
        ],
    }
    url_info = {"document_barcode": "ST00001"}

    # Should not raise
    check_restricted_file(metadata, url_info)


def test_check_restricted_file_rejects_restricted_document():
    """Test that restricted documents raise an error"""
    metadata = {
        "access": settings.ACCESS_PUBLIC,
        "documenten": [
            {"barcode": "ST00001", "access": "RESTRICTED"},
        ],
    }
    url_info = {"document_barcode": "ST00001"}

    with pytest.raises(ImmediateHttpResponse) as exc_info:
        check_restricted_file(metadata, url_info)

    response = exc_info.value.response
    assert response.status_code == 400
    assert response.content.decode() == RESPONSE_CONTENT_RESTRICTED_IN_ZIP


def test_check_restricted_file_rejects_non_public_metadata():
    """Test that non-public metadata raises an error"""
    metadata = {
        "access": "RESTRICTED",
        "documenten": [
            {"barcode": "ST00001", "access": settings.ACCESS_PUBLIC},
        ],
    }
    url_info = {"document_barcode": "ST00001"}

    with pytest.raises(ImmediateHttpResponse) as exc_info:
        check_restricted_file(metadata, url_info)

    response = exc_info.value.response
    assert response.status_code == 400
