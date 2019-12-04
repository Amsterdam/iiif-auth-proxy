from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
def index(request, iiif_url):
    if request.is_authorized_for(settings.EDEPOT_PRIVATE_SCOPE):
        return HttpResponse("APPROVED")
    elif request.is_authorized_for(settings.EDEPOT_PUBLIC_SCOPE):
        # TODO: Get dossiernumber from iiif_url
        # TODO: Get metadata from stadsarchiefserver
        return HttpResponse("APPROVED IF IMAGE IS PUBLIC")
    else:
        return HttpResponse("DENIED", status=401)
