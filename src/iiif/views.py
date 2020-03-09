import logging

from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from . import tools

log = logging.getLogger(__name__)

RESPONSE_CONTENT_NO_TOKEN = "No token supplied"
RESPONSE_CONTENT_NO_DOCUMENT_IN_METADATA = "Document not found in metadata"


@csrf_exempt
def index(request, iiif_url):
    if not request.META.get('HTTP_AUTHORIZATION', None):
        return HttpResponse(RESPONSE_CONTENT_NO_TOKEN, status=401)
    token = request.META['HTTP_AUTHORIZATION']

    try:
        stadsdeel, dossier, document_barcode, file = tools.get_info_from_iiif_url(iiif_url)
    except tools.InvalidIIIFUrlError:
        return HttpResponse("Invalid formatted url", status=400)

    # Get image meta data
    meta_response = tools.get_meta_data(stadsdeel, dossier, token)
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

    # Get the image itself
    headers = {}
    if 'HTTP_X_FORWARDED_PROTO' in request.META and 'HTTP_X_FORWARDED_HOST' in request.META :
        headers['X-Forwarded-Proto'] = request.META['HTTP_X_FORWARDED_PROTO']
        headers['X-Forwarded-Host'] = request.META['HTTP_X_FORWARDED_HOST']
    img_response = tools.get_image_from_iiif_server(iiif_url, headers)
    if img_response.status_code == 404:
        return HttpResponse("No image could be found", status=404)
    elif img_response.status_code != 200:
        log.info(
            f"Got response code {img_response.status_code} while retrieving "
            f"the image {iiif_url} from the iiif-image-server."
        )
        return HttpResponse(
            f"We had a problem retrieving the image. We got status code {img_response.status_code}",
            status=400
        )

    # Check whether the image exists in the metadata and whether it is public
    try:
        is_public = tools.img_is_public(metadata, document_barcode)
    except tools.DocumentNotFoundInMetadataError:
        return HttpResponse(RESPONSE_CONTENT_NO_DOCUMENT_IN_METADATA, status=404)

    # Decide whether the user can view the image
    if request.is_authorized_for(settings.BOUWDOSSIER_EXTENDED_SCOPE):
        # The user has an extended scope, meaning (s)he can view anything. So we'll return the image.
        return HttpResponse(img_response.content, content_type=img_response.headers.get('Content-Type', ''))

    elif request.is_authorized_for(settings.BOUWDOSSIER_READ_SCOPE) and is_public:
        # The user has a read scope, meaning (s)he can view only public images.
        # This image is public, so we'll serve it.
        return HttpResponse(img_response.content, content_type=img_response.headers.get('Content-Type', ''))

    return HttpResponse("", status=401)
