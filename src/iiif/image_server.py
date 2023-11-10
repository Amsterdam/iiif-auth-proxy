import logging
import re

import requests
from django.conf import settings
from django.http import HttpResponse
from requests.exceptions import RequestException

from iiif import zip_tools
from iiif.tools import ImmediateHttpResponse

log = logging.getLogger(__name__)

RESPONSE_CONTENT_ERROR_RESPONSE_FROM_IMAGE_SERVER = \
    "The image-server cannot be reached because the following error occurred: "


def create_wabo_url(url_info, metadata):
    for document in metadata["documenten"]:
        if document["barcode"] == url_info["document_barcode"]:
            return document["bestanden"][0]["filename"]  # there is always only one filename per bestand
    # TODO: raise something in the unlikely event that nothing is found


# TODO: split into two functions, one for url and one for headers
def create_file_url_and_headers(request_meta, url_info, iiif_url, metadata):
    if url_info["source"] == "edepot":

        # If the iiif url contains a reference to dossier like SQ1421 without a '-' or '/' between the letters
        # and the numbers, then this was added as a reference to stadsdeel and dossiernumber and
        # it should be removed. The line below does exactly that.
        iiif_url_edepot = re.sub(r"[A-Z]+\d+/", "", url_info["source_filename"])

        iiif_image_url = f"{settings.EDEPOT_BASE_URL}{iiif_url_edepot}"
        return iiif_image_url, {"Authorization": settings.HCP_AUTHORIZATION}, ()

    elif url_info["source"] == "wabo":
        wabo_url = create_wabo_url(url_info, metadata)
        iiif_image_url = f"{settings.WABO_BASE_URL}{wabo_url}"
        cert = "/tmp/sw444v1912.pem"
        return iiif_image_url, {}, cert


def get_image_from_server(file_url, headers, cert, verify=True):
    return requests.get(
        file_url, headers=headers, cert=cert, verify=verify, timeout=(15, 25)
    )


def get_file(request_meta, url_info, iiif_url, metadata):
    # If we need to get an edepot source file directly from the stadsarchief we need to disable
    # certificate checks because the wildcard cert doesn't include the host name.
    # TODO: remove this once the cert is fixed
    verify = True
    if url_info["source"] == "edepot":
        verify = False

    # Get the file itself
    file_url, headers, cert = create_file_url_and_headers(
        request_meta, url_info, iiif_url, metadata
    )
    try:
        file_response = get_image_from_server(file_url, headers, cert, verify)
    except RequestException as e:
        message = (
            f"{RESPONSE_CONTENT_ERROR_RESPONSE_FROM_IMAGE_SERVER} {e.__class__.__name__}"
        )
        log.error(message)
        raise ImmediateHttpResponse(response=HttpResponse(message, status=502))

    return file_response, file_url


def handle_file_response_codes(file_response, file_url):
    if file_response.status_code == 404:
        raise ImmediateHttpResponse(
            response=HttpResponse(
                f"No source file could be found for the url {file_url}", status=404
            )
        )
    elif file_response.status_code != 200:
        log.info(
            f"Got response code {file_response.status_code} while retrieving "
            f"the image {file_url} from the image server."
        )
        raise ImmediateHttpResponse(
            response=HttpResponse(
                f"We had a problem retrieving the image. We got status "
                f"code {file_response.status_code} for url {file_url}.",
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
    request_meta,
    tmp_folder_path,
):
    info_txt_contents += f"{iiif_url}: "

    if fail_reason:
        info_txt_contents += f"Not included in this zip because {fail_reason}\n"
        return info_txt_contents

    try:
        file_response, file_url = get_file(request_meta, url_info, iiif_url, metadata)
        handle_file_response_codes(file_response, file_url)
    except ImmediateHttpResponse as e:
        log.exception(f"HTTP Exception while retrieving {iiif_url} from the source system: ({e.response.content})")
        info_txt_contents += (
            f"Not included in this zip because an error occurred "
            f"while getting it from the source system\n"
        )
        return info_txt_contents
    except Exception as e:
        log.exception(f"Exception while retrieving {iiif_url} from the source system: ({e}).")
        info_txt_contents += (
            f"Not included in this zip because an error occurred "
            f"while getting it from the source system\n"
        )
        return info_txt_contents

    # Save image file to tmp folder
    zip_tools.save_file_to_folder(
        tmp_folder_path, url_info["filename"], file_response.content
    )
    info_txt_contents += "included\n"

    return info_txt_contents
