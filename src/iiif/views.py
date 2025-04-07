import logging

from django.http import HttpResponse
from django.views.decorators.cache import add_never_cache_headers, patch_cache_control
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.vary import vary_on_headers
from toolz import partial, pipe

from auth_mail import authentication
from iiif import image_server, parsing
from iiif.image_handling import (
    can_generate_default_thumbnail_for,
    crop_image,
    generate_info_json,
    is_image_content_type,
    scale_image,
)
from iiif.image_server import create_non_image_file_thumbnail
from iiif.metadata import get_metadata
from main import utils

log = logging.getLogger(__name__)
HOUR = 3600


def add_caching_headers(is_cacheable, response):
    if is_cacheable:
        patch_cache_control(response, private=True, max_age=HOUR * 36)
    else:
        add_never_cache_headers(response)
    return response


@csrf_exempt
@vary_on_headers("Authorization")
def index(request, iiif_url):
    try:
        authentication.check_auth_availability(request)
        mail_jwt_token, is_mail_login = authentication.read_out_mail_jwt_token(request)
        user_scope = authentication.get_user_scope(request, mail_jwt_token)

        is_source_file_requested = utils.str_to_bool(request.GET.get("source_file"))
        url_info = parsing.get_url_info(iiif_url, is_source_file_requested)

        authentication.check_wabo_for_mail_login(is_mail_login, url_info)
        metadata, _ = get_metadata(url_info, iiif_url, {})

        authentication.check_file_access_in_metadata(metadata, url_info, user_scope)
        is_cacheable = authentication.is_caching_allowed(metadata, url_info)

        file_response, file_url = image_server.get_file(url_info, metadata)
        image_server.handle_file_response_codes(file_response, file_url)

        file_content = file_response.content
        file_type = file_response.headers.get("Content-Type")

        if is_source_file_requested:
            return add_caching_headers(
                is_cacheable, HttpResponse(file_content, file_type)
            )

        if can_generate_default_thumbnail_for(content_type=file_type):
            # The requested file is NOT an image itself, but we can create a thumbnail for it so let's create it.
            file_content = create_non_image_file_thumbnail(file_format="jpeg")
            file_type = "image/jpeg"
        elif not is_image_content_type(file_type):
            # Not an image return a 400
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
            return add_caching_headers(
                is_cacheable,
                HttpResponse(response_content, content_type="application/json"),
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

        return add_caching_headers(is_cacheable, HttpResponse(edited_image, file_type))
    except utils.ImmediateHttpResponse as e:
        log.exception("ImmediateHttpResponse in index:")
        return e.response
