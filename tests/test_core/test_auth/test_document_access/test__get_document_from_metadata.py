import pytest

from core.auth.document_access import _get_document_from_metadata
from core.auth.exceptions import DocumentNotFoundInMetadataError


def test_get_document_from_metadata_success():
    """Test that correct document is returned"""
    metadata = {
        "documenten": [
            {"barcode": "ST00001", "access": "PUBLIC"},
            {"barcode": "ST00002", "access": "RESTRICTED"},
        ]
    }

    result = _get_document_from_metadata(metadata, "ST00002")

    assert result["barcode"] == "ST00002"


def test_get_document_from_metadata_not_found():
    """Test that a DocumentNotFoundInMetadataError is raised when barcode not found"""
    metadata = {
        "documenten": [
            {"barcode": "ST00001", "access": "PUBLIC"},
        ]
    }

    with pytest.raises(DocumentNotFoundInMetadataError):
        _get_document_from_metadata(metadata, "ST99999")


def test_get_document_from_metadata_empty_list():
    """Test that a DocumentNotFoundInMetadataError is raised when list is empty"""
    metadata = {"documenten": []}

    with pytest.raises(DocumentNotFoundInMetadataError):
        _get_document_from_metadata(metadata, "ST00001")
