from django.conf import settings
from django.http import HttpResponse

from core.auth.constants import (
    RESPONSE_CONTENT_COPYRIGHT,
    RESPONSE_CONTENT_INVALID_SCOPE,
    RESPONSE_CONTENT_NO_DOCUMENT_IN_METADATA,
    RESPONSE_CONTENT_RESTRICTED,
)
from core.auth.exceptions import DocumentNotFoundInMetadataError
from main.utils import ImmediateHttpResponse


def _valid_scope_given(scope: str) -> None:
    if scope not in (
        settings.BOUWDOSSIER_PUBLIC_SCOPE,
        settings.BOUWDOSSIER_EXTENDED_SCOPE,
        settings.BOUWDOSSIER_READ_SCOPE,
    ):
        raise ImmediateHttpResponse(
            response=HttpResponse(RESPONSE_CONTENT_INVALID_SCOPE, status=401)
        )


def _get_document_from_metadata(metadata: dict, barcode: str) -> dict:
    """
    Get the data of a document from the metadata by its barcode
    """
    document = next(
        (doc for doc in metadata["documenten"] if doc["barcode"] == barcode), None
    )
    if document is None:
        raise DocumentNotFoundInMetadataError(
            f"Document with barcode '{barcode}' not found"
        )
    return document


def check_file_access_in_metadata(metadata, url_info, scope):
    _valid_scope_given(scope)

    # Check whether the image exists in the metadata
    try:
        is_public, has_copyright = img_is_public_copyright(
            metadata, url_info["document_barcode"]
        )
        if is_public:
            if scope == settings.BOUWDOSSIER_PUBLIC_SCOPE and has_copyright:
                raise ImmediateHttpResponse(
                    response=HttpResponse(RESPONSE_CONTENT_COPYRIGHT, status=401)
                )
        elif scope != settings.BOUWDOSSIER_EXTENDED_SCOPE:
            raise ImmediateHttpResponse(
                response=HttpResponse(RESPONSE_CONTENT_RESTRICTED, status=401)
            )
    except DocumentNotFoundInMetadataError as e:
        raise ImmediateHttpResponse(
            response=HttpResponse(RESPONSE_CONTENT_NO_DOCUMENT_IN_METADATA, status=404)
        ) from e


def is_caching_allowed(metadata, url_info):
    is_public, has_copyright = img_is_public_copyright(
        metadata, url_info["document_barcode"]
    )
    return is_public and not has_copyright


def img_is_public_copyright(metadata, document_barcode):
    """
    Return whether document is public and has copyright.
    If the document is not public the copyright is not used and returned as unknown
    """
    is_public = False
    has_copyright = None
    if metadata["access"] != settings.ACCESS_PUBLIC:
        return is_public, has_copyright

    document = _get_document_from_metadata(metadata, document_barcode)
    if document["access"] == settings.ACCESS_PUBLIC:
        is_public = True
        has_copyright = document.get("copyright") == settings.COPYRIGHT_YES

    return is_public, has_copyright


def file_can_be_zipped(
    metadata: dict, url_info: dict, scope: str
) -> tuple[bool, str | None]:
    """
    Check if a file can be included in a zip file
    """
    try:
        check_file_access_in_metadata(metadata, url_info, scope)
    except ImmediateHttpResponse as e:
        return False, e.response.content.decode("utf-8")

    # Check if a restricted "aanvraag" has been requested
    document_metadata = _get_document_from_metadata(
        metadata, url_info["document_barcode"]
    )

    titel = document_metadata.get("subdossier_titel", "")
    access = document_metadata.get("access", "")

    # Check if it is a restricted "aanvraag" document
    is_aanvraag = titel.lower().startswith("aanvraag")
    is_restricted = access == settings.ACCESS_RESTRICTED

    if is_aanvraag and is_restricted:
        return False, RESPONSE_CONTENT_RESTRICTED

    # All good, the file can be included in the zip
    return True, None
