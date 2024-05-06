import logging

from django.http import HttpResponse
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import csrf_exempt

from auth_mail import authentication
from iiif import image_server, parsing
from iiif.image_handling import crop_image, generate_info_json, scale_image
from iiif.metadata import get_metadata
from main import utils

log = logging.getLogger(__name__)
HOUR = 3600


@csrf_exempt
@cache_control(private=True, max_age=HOUR * 36)
def index(request, iiif_url):
    try:
        authentication.check_auth_availability(request)
        mail_jwt_token, is_mail_login = authentication.read_out_mail_jwt_token(request)
        scope = authentication.get_max_scope(request, mail_jwt_token)
        url_info = parsing.get_url_info(
            iiif_url, utils.str_to_bool(request.GET.get("source_file"))
        )

        authentication.check_wabo_for_mail_login(is_mail_login, url_info)
        metadata, _ = get_metadata(url_info, iiif_url, {})
        authentication.check_file_access_in_metadata(metadata, url_info, scope)
        # TODO image from image_server cached?
        file_response, file_url = image_server.get_file(
            request.META, url_info, iiif_url, metadata
        )
        image_server.handle_file_response_codes(file_response, file_url)

        if url_info["info_json"]:
            response_content = generate_info_json(
                request.build_absolute_uri().split("/info.json")[0],
                file_response.content,
                file_response.headers.get("Content-Type"),
            )
            content_type = "application/json"
        else:
            cropped_content = crop_image(
                file_response.content,
                url_info["source_file"],
                url_info["region"],
                file_response.headers.get("Content-Type"),
            )
            response_content = scale_image(
                cropped_content,
                url_info["source_file"],
                url_info["scaling"],
                file_response.headers.get("Content-Type"),
            )
            content_type = file_response.headers.get("Content-Type")
    except utils.ImmediateHttpResponse as e:
        log.exception("ImmediateHttpResponse in index:")
        return e.response

    return HttpResponse(
        response_content,
        content_type,
    )
