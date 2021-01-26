import logging

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from iiif import tools

log = logging.getLogger(__name__)


@csrf_exempt
def index(request, iiif_url):
    try:
        tools.check_auth_availability(request)
        jwt_token = tools.read_out_jwt_token(request)
        scope = tools.get_max_scope(request, jwt_token)
        url_info = tools.get_url_info(request, iiif_url)
        metadata = tools.get_metadata(url_info, iiif_url)
        tools.check_file_access_in_metadata(metadata, url_info, scope)
        file_response, file_url = tools.get_file(request, url_info, iiif_url, metadata)
        tools.handle_file_response_errors(file_response, file_url)
    except tools.ImmediateHttpResponse as e:
        return e.response

    return HttpResponse(file_response.content, content_type=file_response.headers.get('Content-Type', ''))
