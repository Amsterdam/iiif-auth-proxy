import json
import logging
import re

import requests
from django.conf import settings
from django.http import HttpResponse
from requests.exceptions import RequestException

from iiif import zip_tools
from iiif.tools import ImmediateHttpResponse

log = logging.getLogger(__name__)

RESPONSE_CONTENT_ERROR_RESPONSE_FROM_CANTALOUPE = "The iiif-image-server cannot be reached"


def create_wabo_url(url_info, metadata):
    for document in metadata['documenten']:
        if document['barcode'] == url_info['document_barcode']:
            filename = document['bestanden'][0]['filename']
            if url_info['source_file']:
                # This means that in order to avoid any file conversions we're bypassing cantaloupe
                # and going directly to the source server to get the raw file and serve that
                return f"{filename}"
            else:
                return f"2/{url_info['source']}:{filename.replace('/', '-')}/{url_info['formatting']}"
    # TODO: raise something in the unlikely event that nothing is found


# TODO: split into two functions, one for url and one for headers
def create_file_url_and_headers(request_meta, url_info, iiif_url, metadata):
    iiif_url = iiif_url.replace(' ', '%20')
    headers = {}
    if 'HTTP_X_FORWARDED_PROTO' in request_meta and 'HTTP_X_FORWARDED_HOST' in request_meta:
        # Make sure the iiif-image-server gets the protocol and the host of the initial request so that
        # any other info urls in the response have the correct public url, instead of the
        # local .service.consul url.
        headers['X-Forwarded-Proto'] = request_meta['HTTP_X_FORWARDED_PROTO']
        headers['X-Forwarded-Host'] = request_meta['HTTP_X_FORWARDED_HOST']
    else:
        # Added for local testing. If X-Forwarded-ID is present the iiif imageserver
        # also needs to have the X-Forwarded-Host and or X-Forwarded-Port
        # Otherwise the X-Forwarded-Id is used by iiif image server in the destination URI
        http_host = request_meta.get("HTTP_HOST","").split(':')
        if len(http_host) >= 2:
            headers['X-Forwarded-Host'] = http_host[0]
            headers['X-Forwarded-Port'] = http_host[1]

    if url_info['source'] == 'edepot':
        if url_info['source_file']:
            # This means that in order to avoid any file conversions we're bypassing cantaloupe
            # and going directly to the source server to get the raw file and serve that
            url = settings.EDEPOT_BASE_URL + url_info['filename'].replace('-', '/')
            return url, {'Authorization': settings.HCP_AUTHORIZATION}, ()
        else:
            # If the iiif url contains a reference to dossier like SQ1421 without - then
            # this was added to ad reference to stadsdeel and dossiernumber and it should be removed
            iiif_url_edepot = re.sub(r":[A-Z]+\d+-", ":", iiif_url)
            if iiif_url_edepot != iiif_url:
                headers['X-Forwarded-ID'] = iiif_url.split('/')[1]
            iiif_image_url = f"{settings.IIIF_BASE_URL}:{settings.IIIF_PORT}/iiif/{iiif_url_edepot}"
            return iiif_image_url, headers, ()
    elif url_info['source'] == 'wabo':
        if url_info['source_file']:
            # This means that in order to avoid any file conversions we're bypassing cantaloupe
            # and going directly to the source server to get the raw file and serve that
            wabo_url = create_wabo_url(url_info, metadata)
            iiif_image_url = f"{settings.WABO_BASE_URL}{wabo_url}"
            cert = '/tmp/sw444v1912.pem'
            return iiif_image_url, headers, cert
        else:
            headers['X-Forwarded-ID'] = iiif_url.split('/')[1]
            wabo_url = create_wabo_url(url_info, metadata)
            iiif_image_url = f"{settings.IIIF_BASE_URL}:{settings.IIIF_PORT}/iiif/{wabo_url}"
            return iiif_image_url, headers, ()


def get_image_from_iiif_server(file_url, headers, cert):
    return requests.get(file_url, headers=headers, cert=cert)


def get_file(request_meta, url_info, iiif_url, metadata):
    # Get the file itself
    file_url, headers, cert = create_file_url_and_headers(request_meta, url_info, iiif_url, metadata)
    try:
        file_response = get_image_from_iiif_server(file_url, headers, cert)
    except RequestException as e:
        log.error(
            f"{RESPONSE_CONTENT_ERROR_RESPONSE_FROM_CANTALOUPE} "
            f"because of this error {e}"
        )
        raise ImmediateHttpResponse(response=HttpResponse(RESPONSE_CONTENT_ERROR_RESPONSE_FROM_CANTALOUPE, status=502))

    return file_response, file_url


def handle_file_response_errors(file_response, file_url):
    if file_response.status_code == 404:
        raise ImmediateHttpResponse(
            response=HttpResponse(f"No source file could be found for internal url {file_url}", status=404))
    elif file_response.status_code != 200:
        log.info(
            f"Got response code {file_response.status_code} while retrieving "
            f"the image {file_url} from the iiif-image-server."
        )
        raise ImmediateHttpResponse(response=HttpResponse(
            f"We had a problem retrieving the image. We got status "
            f"code {file_response.status_code} for internal url {file_url}",
            status=400
        ))


def download_files_for_zip(record):
    # Create a tmp folder to store downloaded source files
    zipjob_uuid, tmp_folder_path = zip_tools.create_tmp_folder()

    # Init contents of txt info file which is sent along in the zip
    info_txt_contents = "The following files were requested:\n"

    # Get all the source files and put them in a folder to be zipped afterwards
    for i, (iiif_url, info) in enumerate(record['urls'].items()):

        # Tell cantaloupe we want the full image
        iiif_url += '/full/full/0/default.jpg'

        info_txt_contents += f"{iiif_url}: "
        try:
            file_response, file_url = get_file(
                record['request_meta'], info['url_info'], iiif_url, info['metadata'])
            handle_file_response_errors(file_response, file_url)
        except ImmediateHttpResponse as e:
            log.error(f"Error while retrieving {iiif_url} from the source system: {e.response.content}")
            info_txt_contents += f"Not included in this zip because an error occurred " \
                                 f"while getting it from the source system\n"
            continue
        except Exception as e:
            log.error(f"Error while retrieving {iiif_url} from the source system: {e}")
            info_txt_contents += f"Not included in this zip because an error occurred " \
                                 f"while getting it from the source system\n"
            continue

        # Save image file to tmp folder
        zip_tools.save_file_to_folder(tmp_folder_path, info['url_info']['filename'], file_response.content)
        info_txt_contents += "included\n"

    return tmp_folder_path, info_txt_contents, zipjob_uuid
