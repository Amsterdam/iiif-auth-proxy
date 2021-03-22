import logging

import requests
from django.conf import settings
from django.http import HttpResponse
from requests.exceptions import RequestException

from iiif.tools import ImmediateHttpResponse

log = logging.getLogger(__name__)

RESPONSE_CONTENT_ERROR_RESPONSE_FROM_METADATA_SERVER = "The iiif-metadata-server cannot be reached"


def do_metadata_request(url_info):
    # Test with:
    # curl -i -H "Accept: application/json" http://iiif-metadata-server-api.service.consul:8183/iiif-metadata/bouwdossier/SA85385/
    metadata_url = f"{settings.STADSARCHIEF_META_SERVER_BASE_URL}:" \
                   f"{settings.STADSARCHIEF_META_SERVER_PORT}/iiif-metadata/bouwdossier/{url_info['stadsdeel']}{url_info['dossier']}/"
    return requests.get(metadata_url)


def get_metadata(url_info, iiif_url):
    # Get the image metadata from the metadata server
    try:
        meta_response = do_metadata_request(url_info)
    except RequestException as e:
        log.error(
            f"{RESPONSE_CONTENT_ERROR_RESPONSE_FROM_METADATA_SERVER} "
            f"because of this error {e}"
        )
        raise ImmediateHttpResponse(response=HttpResponse(RESPONSE_CONTENT_ERROR_RESPONSE_FROM_METADATA_SERVER, status=502))

    if meta_response.status_code == 404:
        raise ImmediateHttpResponse(response=HttpResponse("No metadata could be found for this dossier", status=404))
    elif meta_response.status_code != 200:
        log.info(
            f"Got response code {meta_response.status_code} while retrieving "
            f"the metadata for {iiif_url} from the stadsarchief metadata server."
        )
        raise ImmediateHttpResponse(response=HttpResponse(
            f"We had a problem retrieving the metadata. We got status code {meta_response.status_code}",
            status=400
        ))
    metadata = meta_response.json()

    return metadata
