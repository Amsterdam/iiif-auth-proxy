import json
import logging
import re
import urllib

from django.conf import settings
from django.http import HttpResponse, HttpResponseNotAllowed

from iiif.tools import ImmediateHttpResponse

log = logging.getLogger(__name__)


class InvalidIIIFUrlError(Exception):
    pass


def check_for_post(request):
    if request.method != "POST":
        raise ImmediateHttpResponse(response=HttpResponseNotAllowed(['POST']))


def get_info_from_iiif_url(iiif_url, source_file):
    ## PRE-WABO
    # iiif_url = \
    # "https://acc.images.data.amsterdam.nl/iiif/2/edepot:ST-00015-ST00000126_00001.jpg/full/1000,1000/0/default.jpg"
    # ST-00015-ST00000126_00001.jpg=filename  ST=stadsdeel  00015=dossier  ST00000126=document_barcode  00001=file/bestand

    ## WABO
    # iiif_url = \
    # "https://acc.images.data.amsterdam.nl/iiif/2/wabo:SDZ-38657-4900487_628547/full/full/0/default.jpg""
    # SDZ-38657-4900487_628547=filename  SDZ=stadsdeel  38657=dossier  4900487=olo_liaan_nummer  628547=document_barcode

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
                'file': file.split('.')[0],  # The file in the dossier
                'formatting': formatting,
                'source_file': source_file,
                'filename': relevant_url_part,  # The filename if this file needs to be stored on disc
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
                'filename': relevant_url_part,  # The filename if this file needs to be stored on disc
            }

        raise InvalidIIIFUrlError(f"Invalid iiif url (no valid source): {iiif_url}")

    except Exception as e:
        log.error(f"Invalid iiif url: {iiif_url} ({e})")
        raise InvalidIIIFUrlError(f"Invalid iiif url: {iiif_url}")


def get_email_address(request, jwt_token):
    email_address = None
    if request.get_token_subject and '@' in request.get_token_subject:
        email_address = request.get_token_subject
    elif '@' in jwt_token.get('sub', ''):
        email_address = jwt_token['sub']
    elif '@' in jwt_token.get('email', ''):
        email_address = jwt_token['email']

    if email_address is None:
        raise ImmediateHttpResponse(response=HttpResponse("No email address found in tokens", status=400))

    return email_address


def get_url_info(request, iiif_url):
    try:
        url_info = get_info_from_iiif_url(iiif_url, request.GET.get('source_file') == 'true')
    except InvalidIIIFUrlError:
        raise ImmediateHttpResponse(response=HttpResponse("Invalid formatted url", status=400))
    return url_info


def parse_payload(request):
    try:
        return json.loads(request.body.decode("utf-8"))
    except json.decoder.JSONDecodeError:
        raise ImmediateHttpResponse(response=HttpResponse("JSON invalid", status=400))


def check_login_url_payload(payload):
    if not payload.get('email'):
        raise ImmediateHttpResponse(response=HttpResponse("No email found in json", status=400))

    if not payload.get('origin_url'):
        raise ImmediateHttpResponse(response=HttpResponse("No origin_url found in json", status=400))

    origin_url_hostname = urllib.parse.urlparse(payload['origin_url']).hostname
    if origin_url_hostname not in settings.LOGIN_ORIGIN_URL_TLD_WHITELIST:
        raise ImmediateHttpResponse(
            response=HttpResponse(f"origin_url must be one of {settings.LOGIN_ORIGIN_URL_TLD_WHITELIST}", status=400))

    return payload['email'], payload['origin_url']


def check_zip_payload(payload):
    if not payload.get('urls'):
        raise ImmediateHttpResponse(response=HttpResponse("No urls detected in json", status=400))


def strip_full_iiif_url(url):
    if '/iiif/' not in url:
        raise ImmediateHttpResponse(response=HttpResponse("Misformed paths", status=400))

    # Strip the domain from the url and return the only relevant part
    return url.split('/iiif/')[-1]


def check_email_validity(email_address):
    EMAIL_REGEX = re.compile(r"[^@]+@[^@]+\.[^@]+")  # Just basic sanity check for a @ and a dot
    if not EMAIL_REGEX.match(email_address):
        raise ImmediateHttpResponse(response=HttpResponse("Email is not valid", status=400))
