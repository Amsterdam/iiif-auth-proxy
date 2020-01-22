import requests
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from . import tools


@csrf_exempt
def index(request, iiif_url):
    try:
        stadsdeel, dossier, document_barcode, file = tools.get_info_from_iiif_url(iiif_url)
    except tools.InvalidIIIFUrlError:
        return HttpResponse("Invalid formatted url", status=400)

    # Get image meta data
    meta_response = tools.get_meta_data(dossier)
    if meta_response.status_code != 200:
        return HttpResponse("No metadata could be found for this image", status=404)
    # TODO: interpret the xml to get the image "status"
    metadata = meta_response.json()

    # Get the image itself
    img_response = tools.get_image_from_iiif_server(stadsdeel, dossier, document_barcode, file)
    if img_response.status_code != 200:
        return HttpResponse("No image could be found", status=404)

    # Decide whether the user can view the image
    if request.is_authorized_for(settings.BOUWDOSSIER_EXTENDED_SCOPE):
        # The user has an extended scope, meaning (s)he can view anything. So we'll return the image.
        return HttpResponse(img_response.content)

    elif request.is_authorized_for(settings.BOUWDOSSIER_READ_SCOPE) and tools.img_is_public(metadata, document_barcode):
        # The user has a read scope, meaning (s)he can view only public images. This image is public, so we'll serve it.
        return HttpResponse(img_response.content)

    return HttpResponse("", status=401)

