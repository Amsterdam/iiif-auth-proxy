import logging
from functools import partial
from io import BytesIO
from math import floor

import requests
from django.conf import settings
from django.http import HttpResponse
from PIL import Image
from requests.exceptions import RequestException

from main.utils import ImmediateHttpResponse
from zip_consumer import zip_tools

log = logging.getLogger(__name__)

RESPONSE_CONTENT_ERROR_RESPONSE_FROM_IMAGE_SERVER = (
    "The image-server cannot be reached because the following error occurred: "
)


class FilenameNotFoundInDocumentInMetadataError(Exception):
    pass


class FileSourceNotValidError(Exception):
    pass


def get_filename(url_info, metadata):
    # The filename if this file needs to be stored on disc
    for document in metadata["documenten"]:
        if document["barcode"] == url_info["document_barcode"]:
            position = int(url_info["filenr"])
            return document["bestanden"][position]["filename"]
    raise FilenameNotFoundInDocumentInMetadataError(
        f'Filename for document {url_info["document_barcode"]} not found'
    )


def create_url(url_info, metadata):
    for document in metadata["documenten"]:
        if document["barcode"] == url_info["document_barcode"]:
            position = int(url_info["filenr"])
            return document["bestanden"][position]["file_pad"]
    raise FilenameNotFoundInDocumentInMetadataError(
        f'File_pad for document {url_info["document_barcode"]} not found'
    )


def create_file_url_and_headers(url_info, metadata):
    if url_info["source"] == "edepot":
        iiif_url_edepot = create_url(url_info, metadata)
        iiif_image_url = f"{settings.EDEPOT_BASE_URL}{iiif_url_edepot}"
        return iiif_image_url, {"Authorization": settings.EDEPOT_AUTHORIZATION}

    if url_info["source"] == "wabo":
        wabo_url = create_url(url_info, metadata)
        iiif_image_url = f"{settings.WABO_BASE_URL}{wabo_url}"
        return iiif_image_url, {"Authorization": settings.WABO_AUTHORIZATION}

    raise FileSourceNotValidError(f'File source: {url_info["source"]} invalid')


def _get_filename_variants(file_url):
    """
    Generates a list of unique filename variants (original, lowercase, uppercase).

    Removes duplicates when the filename is already all uppercase or lowercase.
    """
    base_url, full_filename = file_url.rsplit("/", maxsplit=1)
    filename, extension = full_filename.rsplit(".", maxsplit=1)

    variants = [
        file_url,
        f"{base_url}/{filename.lower()}.{extension}",
        f"{base_url}/{filename.upper()}.{extension}",
    ]

    return list(dict.fromkeys(variants))


def _create_image(
    file_format: str | None = None,
    size: tuple[int, int] | None = None,
    color: str | int | float = 0,
) -> bytes:
    # Use the given values or the default values
    size = size or (32, 32)

    # Create the mock image
    img = Image.new("RGB", size=size, color=color)
    buf = BytesIO()
    img.save(buf, format=file_format)
    return buf.getvalue()


# Used to create a "default thumbnail" for files that are requested and are not an image itself
create_non_image_file_thumbnail = partial(_create_image, size=(180, 180), color="green")


def get_file(url_info, metadata):
    file_url, headers = create_file_url_and_headers(url_info, metadata)
    file_response = None
    successful_url = None
    last_error = None

    file_url_variants = _get_filename_variants(file_url)
    max_timeout = floor(25 / len(file_url_variants))  # Calculate the correct max_timeout
    for file_url_variant in file_url_variants:
        try:
            file_response = requests.get(
                file_url_variant, headers=headers, verify=False, timeout=(5, max_timeout)
            )
            if file_response.status_code != 404:
                successful_url = file_url_variant
                break
        except RequestException as e:
            log.warning(
                f"Request failed for {file_url_variant}: {e.__class__.__name__}"
            )
            last_error = e

            # Try the next variant
            continue

    # If all variants failed, raise error
    if file_response is None and last_error:
        message = f"{RESPONSE_CONTENT_ERROR_RESPONSE_FROM_IMAGE_SERVER} {last_error.__class__.__name__}"
        log.error(message)
        file_response = HttpResponse(message, status=502)
        raise ImmediateHttpResponse(response=file_response) from last_error

    log.info(f"Reached finally, {file_response=}")
    return file_response, successful_url or file_url


def handle_file_response_codes(file_response, file_url):

    if file_response is None:
        raise ImmediateHttpResponse(
            response=HttpResponse(f"No source file could be found", status=404)
        )

    match file_response.status_code:
        case 404:
            raise ImmediateHttpResponse(
                response=HttpResponse(f"No source file could be found", status=404)
            )
        case 502:
            raise ImmediateHttpResponse(response=file_response)
        case _ if file_response.status_code != 200:
            log.error(
                f"Got response code {file_response.status_code} while retrieving "
                f"the image {file_url} from the image server."
            )
            raise ImmediateHttpResponse(
                response=HttpResponse(
                    f"We had a problem retrieving the image. We got status "
                    f"code {file_response.status_code}",
                    status=502,
                )
            )


def prepare_zip_downloads():
    # Create a tmp folder to store downloaded source files
    zipjob_uuid, tmp_folder_path = zip_tools.create_tmp_folder()

    # Init contents of txt info file which is sent along in the zip
    info_txt_contents = "The following files were requested:\n"

    return zipjob_uuid, tmp_folder_path, info_txt_contents


def download_file_for_zip(
    iiif_url,
    info_txt_contents,
    url_info,
    fail_reason,
    metadata,
    tmp_folder_path,
):
    filename = get_filename(url_info, metadata)
    info_txt_contents += f"{filename}: "

    if fail_reason:
        info_txt_contents += f"Not included in this zip because {fail_reason}\n"
        return info_txt_contents

    try:
        file_response, file_url = get_file(url_info, metadata)
        handle_file_response_codes(file_response, file_url)
    except ImmediateHttpResponse as e:
        log.exception(
            f"HTTP Exception while retrieving {iiif_url} from the source system: ({e.response.content})"
        )
        info_txt_contents += (
            f"Not included in this zip because an error occurred "
            f"while getting it from the source system\n"
        )
        return info_txt_contents
    except Exception as e:
        log.exception(
            f"Exception while retrieving {iiif_url} from the source system: ({e})."
        )
        info_txt_contents += (
            f"Not included in this zip because an error occurred "
            f"while getting it from the source system\n"
        )
        return info_txt_contents

    # Save image file to tmp folder
    zip_tools.save_file_to_folder(tmp_folder_path, filename, file_response.content)
    info_txt_contents += "included\n"

    return info_txt_contents
