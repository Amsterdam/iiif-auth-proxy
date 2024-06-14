import logging

from django.http import HttpResponse
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import csrf_exempt
from toolz import partial, pipe

from auth_mail import authentication
from iiif import image_server, parsing
from iiif.image_handling import (
    crop_image,
    generate_info_json,
    is_image_content_type,
    scale_image,
)
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

        is_source_file_requested = utils.str_to_bool(request.GET.get("source_file"))
        url_info = parsing.get_url_info(iiif_url, is_source_file_requested)

        authentication.check_wabo_for_mail_login(is_mail_login, url_info)
        metadata, _ = get_metadata(url_info, iiif_url, {})
        authentication.check_file_access_in_metadata(metadata, url_info, scope)
        # TODO image from image_server cached?
        file_response, file_url = image_server.get_file(url_info, metadata)
        image_server.handle_file_response_codes(file_response, file_url)

        file_content = file_response.content
        file_type = file_response.headers.get("Content-Type")

        if is_source_file_requested:
            return HttpResponse(
                file_content,
                file_type,
            )

        if not is_image_content_type(file_type):
            raise utils.ImmediateHttpResponse(
                response=HttpResponse(
                    "Content-type of requested file not supported", status=400
                )
            )

        if url_info["info_json"]:
            response_content = generate_info_json(
                request.build_absolute_uri().split("/info.json")[0],
                file_content,
                file_type,
            )
            return HttpResponse(
                response_content,
                content_type="application/json",
            )

        crop = partial(
            crop_image,
            file_type,
            url_info["region"],
        )
        scale = partial(
            scale_image,
            file_type,
            url_info["scaling"],
        )
        edited_image = pipe(file_content, crop, scale)

        return HttpResponse(
            edited_image,
            file_type,
        )
    except utils.ImmediateHttpResponse as e:
        log.exception("ImmediateHttpResponse in index:")
        return e.response
