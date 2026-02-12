import logging

import requests
from django.conf import settings
from django.http import HttpResponse
from requests.exceptions import RequestException

from main.utils import ImmediateHttpResponse

log = logging.getLogger(__name__)

RESPONSE_CONTENT_ERROR_RESPONSE_FROM_METADATA_SERVER = "The iiif-metadata-server cannot be reached"


def get_metadata_url(url_info):
    # Test with:
    # curl -i -H "Accept: application/json" http://app-iiif-metadata-server/iiif-metadata/bouwdossier/SA85385/
    return (
        f"{settings.METADATA_SERVER_BASE_URL}/iiif-metadata/bouwdossier/{url_info['stadsdeel']}_{url_info['dossier']}/"  # noqa: E501
    )


def do_metadata_request(metadata_url):
    return requests.get(metadata_url, timeout=(15, 25))


def get_metadata(url_info, iiif_url, metadata_cache):
    # Check whether the metadata is already in the cache
    cache_key = f"{url_info['stadsdeel']}_{url_info['dossier']}"
    metadata = metadata_cache.get(cache_key)
    if metadata:
        return metadata, metadata_cache

    # Get the image metadata from the metadata server
    try:
        metadata_url = get_metadata_url(url_info)
        meta_response = do_metadata_request(metadata_url)
    except RequestException as e:
        log.error(f"{RESPONSE_CONTENT_ERROR_RESPONSE_FROM_METADATA_SERVER} because of this error {e}")
        raise ImmediateHttpResponse(
            response=HttpResponse(RESPONSE_CONTENT_ERROR_RESPONSE_FROM_METADATA_SERVER, status=502)
        ) from e

    if meta_response.status_code == 404:
        raise ImmediateHttpResponse(response=HttpResponse("No metadata could be found for this dossier", status=404))
    if meta_response.status_code != 200:
        log.info(
            f"Got response code {meta_response.status_code} while retrieving "
            f"the metadata for {iiif_url} from the stadsarchief metadata server "
            f"on url {metadata_url}."
        )
        raise ImmediateHttpResponse(
            response=HttpResponse(
                f"We had a problem retrieving the metadata. We got status code {meta_response.status_code}",
                status=400,
            )
        )
    metadata = meta_response.json()

    # Store the metadata in the cache so that it can be used while getting many
    # files for a zip
    metadata_cache[cache_key] = metadata

    return metadata, metadata_cache
