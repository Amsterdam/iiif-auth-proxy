import requests
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from .tools import get_info_from_iiif_url, InvalidIIIFUrlError, get_img_status_from_metadata


@csrf_exempt
def index(request, iiif_url):
    try:
        stadsdeel, dossier, subdossier, image = get_info_from_iiif_url(iiif_url)
    except InvalidIIIFUrlError:
        return HttpResponse("Invalid formatted url", status=400)

    # Get image meta data
    meta_response = requests.get(f"{settings.STADSARCHIEF_META_SERVER_URL}{stadsdeel}/{dossier}/{subdossier}/{image}")
    if meta_response.status_code != 200:
        return HttpResponse("No metadata could be found for this image", status=404)
    # TODO: interpret the xml to get the image "status"
    meta_data = meta_response.text

    # Get the image itself
    img_response = requests.get(f"{settings.IIIF_URL}{stadsdeel}/{dossier}/{subdossier}/{image}")
    if img_response.status_code != 200:
        return HttpResponse("No image could be found", status=404)

    # Decide whether the user can view the image
    if request.is_authorized_for(settings.BOUWDOSSIER_ALL_SCOPE):
        return HttpResponse(img_response.content)
    elif request.is_authorized_for(settings.BOUWDOSSIER_OPENBAAR_SCOPE) \
            and get_img_status_from_metadata(meta_data) != "private":
        return HttpResponse(img_response.content)
    else:
        return HttpResponse("DENIED", status=401)
