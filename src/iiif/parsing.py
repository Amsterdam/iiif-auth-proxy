import json
import logging
import re
import urllib

from django.conf import settings
from django.http import HttpResponse, HttpResponseNotAllowed

from main.utils import ImmediateHttpResponse

log = logging.getLogger(__name__)


class InvalidIIIFUrlError(Exception):
    pass


def check_for_post(request):
    if request.method != "POST":
        raise ImmediateHttpResponse(response=HttpResponseNotAllowed(["POST"]))


def get_info_from_iiif_url(iiif_url, source_file):
    """
    # PRE-WABO

    "https://acc.bouwdossiers.amsterdam.nl/iiif/2/edepot:ST_00015~ST00000126_00001.jpg/info.json"

    For the url above it means they request just the info.json, nothing else. More info about the rest
    of this url see the explanation below.

    "https://acc.bouwdossiers.amsterdam.nl/iiif/2/edepot:ST_00015~ST00000126_00001.jpg/full/1000,900/0/default.jpg"

    For the url above, the following information can be extracted:
    - ST_00015~ST00000126_00001.jpg=filename  ST=stadsdeel  00015=dossier  ST00000126=document_barcode  00001=file/bestand
    - full: no cropping
    - 1000,900: scaling the image to fit within a 1000x900 (1000 width, 900 height) pixel bounding box, preserving its aspect ratio
    - 0: rotation angle in degrees
    - default.jpg: default quality, meaning the original quality

    # WABO

    "https://acc.bouwdossiers.amsterdam.nl/iiif/2/wabo:SDZ_TA-38657~4900487_628547/full/full/0/default.jpg""
    - SDZ=stadsdeel
    - TA-38657=dossier
    4900487=olo_liaan_nummer
    628547=document_barcode

    At the end of the url, this can be appended '?source_file=true', which means we'll bypass
    all image related code and go directly for the source file. This can be needed when the file is
    not an image, but for example a txt, xls, zip or something else.
    """

    try:
        source = iiif_url.split(":")[0].split("/")[1]  # "edepot" or "wabo"
        relevant_url_part = iiif_url.split(":")[1].split("/")[0].replace(" ", "%20")
        formatting = (
            iiif_url.split(":")[1].split("/", 1)[1].split("?")[0]
            if "/" in iiif_url.split(":")[1]
            else ""
        )

        info_json = False
        scaling = None
        region = None
        if formatting == "info.json":
            info_json = True
            formatting = None
        elif "/" in formatting:
            region = formatting.split("/")[0]
            scaling = formatting.split("/")[1]
        elif source_file:
            pass
        else:
            raise InvalidIIIFUrlError(
                f"No formatting or info.json provided in iiif url: {iiif_url}"
            )

        url_info = {
            "source": source,
            "formatting": formatting,
            "region": region,
            "scaling": scaling,
            "info_json": info_json,  # Whether the info.json is requested instead of the image itself
        }
        stadsdeel_dossier, olo_and_document = relevant_url_part.split("~")
        stadsdeel, dossier = stadsdeel_dossier.split("_")
        document_barcode, filenr = olo_and_document.split("_")
        return {
            **url_info,
            "stadsdeel": stadsdeel,
            "dossier": dossier,
            "document_barcode": document_barcode,
            "filenr": filenr,
        }

    except Exception as e:
        log.error(f"Invalid iiif url: {iiif_url} ({e})")
        raise InvalidIIIFUrlError(f"Invalid iiif url: {iiif_url}") from e


def get_email_address(request, jwt_token):
    email_address = None
    if request.get_token_subject and "@" in request.get_token_subject:
        email_address = request.get_token_subject
    elif "@" in jwt_token.get("sub", ""):
        email_address = jwt_token["sub"]
    elif "@" in request.get_token_claims.get("email", ""):
        email_address = request.get_token_claims["email"]

    if email_address is None:
        raise ImmediateHttpResponse(
            response=HttpResponse("No email address found in tokens", status=400)
        )

    return email_address


def get_url_info(iiif_url, source_file):
    try:
        url_info = get_info_from_iiif_url(iiif_url, source_file)
    except InvalidIIIFUrlError as e:
        raise ImmediateHttpResponse(
            response=HttpResponse("Invalid formatted url", status=400)
        ) from e
    return url_info


def parse_payload(request):
    try:
        return json.loads(request.body.decode("utf-8"))
    except json.decoder.JSONDecodeError as e:
        raise ImmediateHttpResponse(
            response=HttpResponse("JSON invalid", status=400)
        ) from e


def check_login_url_payload(payload):
    if not payload.get("email"):
        raise ImmediateHttpResponse(
            response=HttpResponse("No email found in json", status=400)
        )

    if not payload.get("origin_url"):
        raise ImmediateHttpResponse(
            response=HttpResponse("No origin_url found in json", status=400)
        )

    origin_url_hostname = urllib.parse.urlparse(payload["origin_url"]).hostname
    if origin_url_hostname not in settings.LOGIN_ORIGIN_URL_TLD_WHITELIST:
        raise ImmediateHttpResponse(
            response=HttpResponse(
                f"origin_url must be one of {settings.LOGIN_ORIGIN_URL_TLD_WHITELIST}",
                status=400,
            )
        )

    return payload["email"], payload["origin_url"]


def check_zip_payload(payload):
    if not payload.get("urls"):
        raise ImmediateHttpResponse(
            response=HttpResponse("No urls detected in json", status=400)
        )


def strip_full_iiif_url(url):
    if "/iiif/" not in url:
        raise ImmediateHttpResponse(
            response=HttpResponse("Misformed paths", status=400)
        )

    # Strip the domain from the url and return the only relevant part
    return url.split("/iiif/")[-1]


def check_email_validity(email_address):
    is_email_regex = re.compile(
        r"[^@]+@[^@]+\.[^@]+"
    )  # Just basic sanity check for a @ and a dot
    if not is_email_regex.match(email_address):
        raise ImmediateHttpResponse(
            response=HttpResponse("Email is not valid", status=400)
        )
