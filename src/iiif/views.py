import logging

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from iiif import tools

log = logging.getLogger(__name__)


@csrf_exempt
def index(request, iiif_url):
    response = tools.check_auth_availability(request)
    if response:
        return response

    jwt_token, response = tools.read_out_jwt_token(request)
    if response:
        return response

    scope, response = tools.define_scope(request, jwt_token)
    if response:
        return response

    url_info, response = tools.get_url_info(request, iiif_url)
    if response:
        return response

    metadata, response = tools.get_metadata(url_info, iiif_url)
    if response:
        return response

    response = tools.check_file_in_metadata(metadata, url_info, scope)
    if response:
        return response

    file_response, file_url, response = tools.get_file(request, url_info, iiif_url, metadata)
    if response:
        return response

    response = tools.handle_file_response_errors(file_response, file_url)
    if response:
        return response

    return HttpResponse(file_response.content, content_type=file_response.headers.get('Content-Type', ''))
