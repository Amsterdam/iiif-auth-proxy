import authorization_django
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from settings.settings import JWKS_TEST_KEY, EDEPOT_PUBLIC_SCOPE, EDEPOT_PRIVATE_SCOPE


@csrf_exempt
def index(request, iiif_url):
    if request.is_authorized_for(EDEPOT_PRIVATE_SCOPE):
        return HttpResponse("APPROVED")
    elif request.is_authorized_for(EDEPOT_PUBLIC_SCOPE):
        # TODO: Get dossiernumber from iiif_url
        # TODO: Get metadata from stadsarchiefserver
        return HttpResponse("APPROVED IF IMAGE IS PUBLIC")
    else:
        return HttpResponse("DENIED", status=401)
