import logging
from datetime import datetime

import jwt
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from jwt.exceptions import ExpiredSignatureError, InvalidSignatureError
from requests.exceptions import RequestException

from iiif import tools

log = logging.getLogger(__name__)

RESPONSE_CONTENT_NO_TOKEN = "No token supplied"
RESPONSE_CONTENT_JWT_TOKEN_EXPIRED = "Your token has expired. Request a new token."
RESPONSE_CONTENT_NO_DOCUMENT_IN_METADATA = "Document not found in metadata"
RESPONSE_CONTENT_ERROR_RESPONSE_FROM_METADATA_SERVER = "The iiif-metadata-server cannot be reached"
RESPONSE_CONTENT_ERROR_RESPONSE_FROM_CANTALOUPE = "The iiif-image-server cannot be reached"


@csrf_exempt
def index(request, iiif_url):
    if not request.META.get('HTTP_AUTHORIZATION') and not request.GET.get('auth'):
        return HttpResponse(RESPONSE_CONTENT_NO_TOKEN, status=401)

    # Check the jwt token if necessary
    jwt_token = {}
    if not request.META.get('HTTP_AUTHORIZATION'):
        # Check signature
        try:
            jwt_token = jwt.decode(request.GET.get('auth'), settings.SECRET_KEY, algorithms=["HS256"])
        except ExpiredSignatureError:
            return HttpResponse("Expired JWT token signature", status=401)
        except InvalidSignatureError:
            return HttpResponse("Invalid JWT token signature", status=401)

        # Check scope
        if jwt_token.get('scope') not in (settings.BOUWDOSSIER_READ_SCOPE, settings.BOUWDOSSIER_EXTENDED_SCOPE):
            return HttpResponse("Invalid scope", status=401)

    if request.is_authorized_for(settings.BOUWDOSSIER_EXTENDED_SCOPE) or jwt_token.get('scope') == settings.BOUWDOSSIER_EXTENDED_SCOPE:
        scope = settings.BOUWDOSSIER_EXTENDED_SCOPE
    elif request.is_authorized_for(settings.BOUWDOSSIER_READ_SCOPE) or jwt_token.get('scope') == settings.BOUWDOSSIER_READ_SCOPE:
        scope = settings.BOUWDOSSIER_READ_SCOPE
    else:
        return HttpResponse("Invalid scope", status=401)

    try:
        url_info = tools.get_info_from_iiif_url(iiif_url, request.GET.get('source_file') == 'true')
    except tools.InvalidIIIFUrlError:
        return HttpResponse("Invalid formatted url", status=400)

    # Get image meta data
    try:
        meta_response = tools.get_meta_data(url_info)
    except RequestException as e:
        log.error(
            f"{RESPONSE_CONTENT_ERROR_RESPONSE_FROM_METADATA_SERVER} "
            f"because of this error {e}"
        )
        return HttpResponse(RESPONSE_CONTENT_ERROR_RESPONSE_FROM_METADATA_SERVER, status=502)

    if meta_response.status_code == 404:
        return HttpResponse("No metadata could be found for this file", status=404)
    elif meta_response.status_code != 200:
        log.info(
            f"Got response code {meta_response.status_code} while retrieving "
            f"the metadata for {iiif_url} from the stadsarchief metadata server."
        )
        return HttpResponse(
            f"We had a problem retrieving the metadata. We got status code {meta_response.status_code}",
            status=400
        )
    metadata = meta_response.json()

    # Check whether the image exists in the metadata and whether it is public
    try:
        is_public = tools.img_is_public(metadata, url_info['document_barcode'])
    except tools.DocumentNotFoundInMetadataError:
        return HttpResponse(RESPONSE_CONTENT_NO_DOCUMENT_IN_METADATA, status=404)

    if not scope == settings.BOUWDOSSIER_EXTENDED_SCOPE and not (is_public and scope == settings.BOUWDOSSIER_READ_SCOPE):
        return HttpResponse("", status=401)

    # Get the file itself
    file_url, headers, cert = tools.create_file_url_and_headers(request.META, url_info, iiif_url, metadata)
    try:
        file_response = tools.get_image_from_iiif_server(file_url, headers, cert)
    except RequestException as e:
        log.error(
            f"{RESPONSE_CONTENT_ERROR_RESPONSE_FROM_CANTALOUPE} "
            f"because of this error {e}"
        )
        return HttpResponse(RESPONSE_CONTENT_ERROR_RESPONSE_FROM_CANTALOUPE, status=502)
    if file_response.status_code == 404:
        return HttpResponse(f"No source file could be found for internal url {file_url}", status=404)
    elif file_response.status_code != 200:
        log.info(
            f"Got response code {file_response.status_code} while retrieving "
            f"the image {file_url} from the iiif-image-server."
        )
        return HttpResponse(
            f"We had a problem retrieving the image. We got status code {file_response.status_code} for "
            f"internal url {file_url}",
            status=400
        )
    return HttpResponse(file_response.content, content_type=file_response.headers.get('Content-Type', ''))
