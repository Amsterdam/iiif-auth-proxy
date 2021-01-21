import logging
from requests.exceptions import RequestException
from jwt.exceptions import ExpiredSignatureError, InvalidSignatureError
import calendar
import re
from datetime import datetime, timedelta
from django.http import HttpResponse
import jwt
import requests
from django.conf import settings

log = logging.getLogger(__name__)


RESPONSE_CONTENT_NO_TOKEN = "No token supplied"
RESPONSE_CONTENT_JWT_TOKEN_EXPIRED = "Your token has expired. Request a new token."
RESPONSE_CONTENT_NO_DOCUMENT_IN_METADATA = "Document not found in metadata"
RESPONSE_CONTENT_ERROR_RESPONSE_FROM_METADATA_SERVER = "The iiif-metadata-server cannot be reached"
RESPONSE_CONTENT_ERROR_RESPONSE_FROM_CANTALOUPE = "The iiif-image-server cannot be reached"



class InvalidIIIFUrlError(Exception):
    pass


class DocumentNotFoundInMetadataError(Exception):
    pass


def get_meta_data(url_info):
    # Test with:
    # curl -i -H "Accept: application/json" http://iiif-metadata-server-api.service.consul:8183/iiif-metadata/bouwdossier/SA85385/
    metadata_url = f"{settings.STADSARCHIEF_META_SERVER_BASE_URL}:" \
                   f"{settings.STADSARCHIEF_META_SERVER_PORT}/iiif-metadata/bouwdossier/{url_info['stadsdeel']}{url_info['dossier']}/"
    return requests.get(metadata_url)


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
        # If the iiif url contains a reference to dossier like SQ1421 without - then
        # this was added to ad reference to stadsdeel and dossiernumber and it should be removed
        iiif_url_edepot = re.sub(r":[A-Z]+\d+-", ":", iiif_url)
        if iiif_url_edepot != iiif_url:
            headers['X-Forwarded-ID'] = iiif_url.split('/')[1]
        iiif_image_url = f"{settings.IIIF_BASE_URL}:{settings.IIIF_PORT}/iiif/{iiif_url_edepot}"
        return iiif_image_url, headers, ()
    elif url_info['source'] == 'wabo':
        if url_info['source_file'] == True:
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


def get_info_from_iiif_url(iiif_url, source_file):
    ## PRE-WABO
    # iiif_url = \
    # "https://acc.images.data.amsterdam.nl/iiif/2/edepot:ST-00015-ST00000126_00001.jpg/full/1000,1000/0/default.jpg"
    # ST=stadsdeel  00015=dossier  ST00000126=document_barcode  00001=file/bestand

    ## WABO
    # iiif_url = \
    # "https://acc.images.data.amsterdam.nl/iiif/2/wabo:SDZ-38657-4900487_628547/full/full/0/default.jpg""
    # SDZ=stadsdeel  38657=dossier  4900487=olo_liaan_nummer  628547=document_barcode

    # At the end of the url, this can be appended '?source_file=true', which means we'll bypass
    # cantaloupe and go directly for the source file

    try:
        source = iiif_url.split(':')[0].split('/')[1]  # "edepot" or "wabo"
        relevant_url_part = iiif_url.split(':')[1].split('/')[0]
        formatting = iiif_url.split(':')[1].split('/', 1)[1].split('?')[0] if '/' in iiif_url.split(':')[1] else ''

        if source == 'edepot':  # == pre-wabo
            m = re.match(r"^([A-Z]+)-?(\d+)-(.+)$", relevant_url_part)
            if not m:
                raise InvalidIIIFUrlError(f"Invalid iiif url (no valid source): {iiif_url}")
            stadsdeel = m.group(1)
            dossier = m.group(2)
            document_and_file = m.group(3).split('-')[-1]
            document_barcode, file = document_and_file.split('_')
            return {
                'source': source,
                'stadsdeel': stadsdeel,
                'dossier': dossier,
                'document_barcode': document_barcode,
                'file': file.split('.')[0],
                'formatting': formatting,
                'source_file': source_file,
            }

        elif source == 'wabo':  # = pre-wabo
            stadsdeel, dossier, olo_and_document = relevant_url_part.split('-', 2)
            olo, document_barcode = olo_and_document.split('_', 1)
            return {
                'source': source,
                'stadsdeel': stadsdeel,
                'dossier': dossier,
                'olo': olo,
                'document_barcode': document_barcode,
                'formatting': formatting,
                'source_file': source_file,
            }

        raise InvalidIIIFUrlError(f"Invalid iiif url (no valid source): {iiif_url}")

    except Exception as e:
        raise InvalidIIIFUrlError(f"Invalid iiif url: {iiif_url}")


def img_is_public(metadata, document_barcode):
    if metadata['access'] != settings.ACCESS_PUBLIC:
        return False

    for meta_document in metadata['documenten']:
        if meta_document['barcode'] == document_barcode:
            if meta_document['access'] == settings.ACCESS_PUBLIC:
                return True
            elif meta_document['access'] == settings.ACCESS_RESTRICTED:
                return False
            break
    raise DocumentNotFoundInMetadataError()


def get_authentication_jwt(expiry_hours=24, key=settings.SECRET_KEY):
    exp = calendar.timegm((datetime.now() + timedelta(hours=expiry_hours)).timetuple())
    return jwt.encode({"exp": exp, "scope": 'BD/R'}, key, algorithm="HS256")


def check_auth_availability(request):
    if not request.META.get('HTTP_AUTHORIZATION') and not request.GET.get('auth'):
        return HttpResponse(RESPONSE_CONTENT_NO_TOKEN, status=401)


def read_out_jwt_token(request):
    jwt_token = {}
    response = None
    if not request.META.get('HTTP_AUTHORIZATION'):
        try:
            jwt_token = jwt.decode(request.GET.get('auth'), settings.SECRET_KEY, algorithms=["HS256"])
            # Check scope
            if jwt_token.get('scope') not in (settings.BOUWDOSSIER_READ_SCOPE, settings.BOUWDOSSIER_EXTENDED_SCOPE):
                response = HttpResponse("Invalid scope", status=401)
        except ExpiredSignatureError:
            response = HttpResponse("Expired JWT token signature", status=401)
        except InvalidSignatureError:
            response = HttpResponse("Invalid JWT token signature", status=401)

    return jwt_token, response


def define_scope(request, jwt_token):
    scope = response =None
    if request.is_authorized_for(settings.BOUWDOSSIER_EXTENDED_SCOPE) \
            or jwt_token.get('scope') == settings.BOUWDOSSIER_EXTENDED_SCOPE:
        scope = settings.BOUWDOSSIER_EXTENDED_SCOPE
    elif request.is_authorized_for(settings.BOUWDOSSIER_READ_SCOPE) \
            or jwt_token.get('scope') == settings.BOUWDOSSIER_READ_SCOPE:
        scope = settings.BOUWDOSSIER_READ_SCOPE
    else:
        response = HttpResponse("Invalid scope", status=401)

    return scope, response


def get_url_info(request, iiif_url):
    url_info = response = None
    try:
        url_info = get_info_from_iiif_url(iiif_url, request.GET.get('source_file') == 'true')
    except InvalidIIIFUrlError:
        response = HttpResponse("Invalid formatted url", status=400)
    return url_info, response


def get_metadata(url_info, iiif_url):
    response = meta_response = metadata = None

    # Get the image metadata from the metadata server
    try:
        meta_response = get_meta_data(url_info)
    except RequestException as e:
        log.error(
            f"{RESPONSE_CONTENT_ERROR_RESPONSE_FROM_METADATA_SERVER} "
            f"because of this error {e}"
        )
        response = HttpResponse(RESPONSE_CONTENT_ERROR_RESPONSE_FROM_METADATA_SERVER, status=502)

    if meta_response:
        if meta_response.status_code == 404:
            response = HttpResponse("No metadata could be found for this file", status=404)
        elif meta_response.status_code != 200:
            log.info(
                f"Got response code {meta_response.status_code} while retrieving "
                f"the metadata for {iiif_url} from the stadsarchief metadata server."
            )
            response = HttpResponse(
                f"We had a problem retrieving the metadata. We got status code {meta_response.status_code}",
                status=400
            )
        metadata = meta_response.json()

    return metadata, response


def check_file_in_metadata(metadata, url_info, scope):
    response = None

    # Check whether the image exists in the metadata
    try:
        is_public = img_is_public(metadata, url_info['document_barcode'])
        # Check whether the file is public
        if not scope == settings.BOUWDOSSIER_EXTENDED_SCOPE \
                and not (is_public and scope == settings.BOUWDOSSIER_READ_SCOPE):
            response = HttpResponse("", status=401)
    except DocumentNotFoundInMetadataError:
        response = HttpResponse(RESPONSE_CONTENT_NO_DOCUMENT_IN_METADATA, status=404)

    return response


def get_file(request, url_info, iiif_url, metadata):
    response = None
    file_response = None

    # Get the file itself
    file_url, headers, cert = create_file_url_and_headers(request.META, url_info, iiif_url, metadata)
    try:
        file_response = get_image_from_iiif_server(file_url, headers, cert)
    except RequestException as e:
        log.error(
            f"{RESPONSE_CONTENT_ERROR_RESPONSE_FROM_CANTALOUPE} "
            f"because of this error {e}"
        )
        response = HttpResponse(RESPONSE_CONTENT_ERROR_RESPONSE_FROM_CANTALOUPE, status=502)

    return file_response, file_url, response


def handle_file_response_errors(file_response, file_url):
    response = None
    if file_response.status_code == 404:
        response = HttpResponse(f"No source file could be found for internal url {file_url}", status=404)
    elif file_response.status_code != 200:
        log.info(
            f"Got response code {file_response.status_code} while retrieving "
            f"the image {file_url} from the iiif-image-server."
        )
        response = HttpResponse(
            f"We had a problem retrieving the image. We got status "
            f"code {file_response.status_code} for internal url {file_url}",
            status=400
        )
    return response
