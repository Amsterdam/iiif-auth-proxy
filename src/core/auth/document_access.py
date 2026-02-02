from django.conf import settings
from django.http import HttpResponse

from core.auth.constants import (
    RESPONSE_CONTENT_COPYRIGHT,
    RESPONSE_CONTENT_INVALID_SCOPE,
    RESPONSE_CONTENT_NO_DOCUMENT_IN_METADATA,
    RESPONSE_CONTENT_RESTRICTED,
    RESPONSE_CONTENT_RESTRICTED_IN_ZIP,
)
from core.auth.exceptions import DocumentNotFoundInMetadataError
from main.utils import ImmediateHttpResponse, find


def check_file_access_in_metadata(metadata, url_info, scope):
    if scope not in (
        settings.BOUWDOSSIER_PUBLIC_SCOPE,
        settings.BOUWDOSSIER_EXTENDED_SCOPE,
        settings.BOUWDOSSIER_READ_SCOPE,
    ):
        raise ImmediateHttpResponse(
            response=HttpResponse(RESPONSE_CONTENT_INVALID_SCOPE, status=401)
        )
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


def check_restricted_file(metadata, url_info):
    is_public, _ = img_is_public_copyright(metadata, url_info["document_barcode"])
    if not is_public:
        raise ImmediateHttpResponse(
            response=HttpResponse(RESPONSE_CONTENT_RESTRICTED_IN_ZIP, status=400)
        )


def img_is_public_copyright(metadata, document_barcode):
    """
    Return whether document is public and has copyright.
    If the document is not public the copyright is not used and returned as unknown
    """
    is_public = False
    has_copyright = None
    if metadata["access"] != settings.ACCESS_PUBLIC:
        return is_public, has_copyright

    document = find(lambda d: d["barcode"] == document_barcode, metadata["documenten"])
    if not document:
        raise DocumentNotFoundInMetadataError()

    if document["access"] == settings.ACCESS_PUBLIC:
        is_public = True
        has_copyright = document.get("copyright") == settings.COPYRIGHT_YES

    return is_public, has_copyright
