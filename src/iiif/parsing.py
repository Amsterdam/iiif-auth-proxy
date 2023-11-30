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
        raise ImmediateHttpResponse(response=HttpResponseNotAllowed(["POST"]))


def get_info_from_iiif_url(iiif_url, source_file):
    """
    # PRE-WABO

    "https://acc.bouwdossiers.amsterdam.nl/iiif/2/edepot:ST-00015-ST00000126_00001.jpg/info.json"

    For the url above it means they request just the info.json, nothing else. More info about the rest
    of this url see the explanation below.

    "https://acc.bouwdossiers.amsterdam.nl/iiif/2/edepot:ST-00015-ST00000126_00001.jpg/full/1000,900/0/default.jpg"

    For the url above, the following information can be extracted:
    - ST-00015-ST00000126_00001.jpg=filename  ST=stadsdeel  00015=dossier  ST00000126=document_barcode  00001=file/bestand
    - full: no cropping
    - 1000,900: scaling the image to fit within a 1000x900 (1000 width, 900 height) pixel bounding box, preserving its aspect ratio
    - 0: rotation angle in degrees
    - default.jpg: default quality, meaning the original quality

    # WABO

    "https://acc.bouwdossiers.amsterdam.nl/iiif/2/wabo:SDZ-38657-4900487_628547/full/full/0/default.jpg""
    - SDZ-38657-4900487_628547=filename
    - SDZ=stadsdeel
    - 38657=dossier
    4900487=olo_liaan_nummer
    628547=document_barcode

    At the end of the url, this can be appended '?source_file=true', which means we'll bypass
    all image related code and go directly for the source file. This can be needed when the file is
    not an image, but for example a txt, xls, zip or something else.
    """

    try:
        source = iiif_url.split(":")[0].split("/")[1]  # "edepot" or "wabo"
        relevant_url_part = iiif_url.split(":")[1].split("/")[0].replace(" ", "%20")
        source_filename = relevant_url_part.replace("-", "/", 2)
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

        if source == "edepot":  # aka pre-wabo
            m = re.match(r"^([A-Z]+)-?(\d+)-(.+)$", relevant_url_part)
            if not m:
                raise InvalidIIIFUrlError(
                    f"Invalid iiif url (no valid source): {iiif_url}"
                )
            stadsdeel = m.group(1)
            dossier = m.group(2)
            document_and_file = m.group(3).split("-")[-1]
            document_barcode, file = document_and_file.split("_")
            return {
                "source": source,
                "stadsdeel": stadsdeel,
                "dossier": dossier,
                "document_barcode": document_barcode,
                "file": file.split(".")[0],  # The file in the dossier
                "formatting": formatting,
                "region": region,
                "scaling": scaling,
                "source_file": source_file,  # Bool whether the file should be served without image processing (pdf/xls)
                "source_filename": source_filename,  # The filename on the source system
                "filename": relevant_url_part,  # The filename if this file needs to be stored on disc
                "info_json": info_json,  # Whether the info.json is requested instead of the image itself
            }

        elif source == "wabo":
            stadsdeel, dossier, olo_and_document = relevant_url_part.split("-", 2)
            olo, document_barcode = olo_and_document.split("_", 1)
            return {
                "source": source,
                "stadsdeel": stadsdeel,
                "dossier": dossier,
                "olo": olo,
                "document_barcode": document_barcode,
                "formatting": formatting,
                "region": region,
                "scaling": scaling,
                "source_file": source_file,  # Bool whether the file should be served without image processing (pdf/xls)
                "source_filename": source_filename,  # The filename on the source system
                "filename": relevant_url_part,  # The filename if this file needs to be stored on disc
                "info_json": info_json,
            }

        raise InvalidIIIFUrlError(f"Invalid iiif url (no valid source): {iiif_url}")

    except Exception as e:
        log.error(f"Invalid iiif url: {iiif_url} ({e})")
        raise InvalidIIIFUrlError(f"Invalid iiif url: {iiif_url}")


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
    except InvalidIIIFUrlError:
        raise ImmediateHttpResponse(
            response=HttpResponse("Invalid formatted url", status=400)
        )
    return url_info


def parse_payload(request):
    try:
        return json.loads(request.body.decode("utf-8"))
    except json.decoder.JSONDecodeError:
        raise ImmediateHttpResponse(response=HttpResponse("JSON invalid", status=400))


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
    EMAIL_REGEX = re.compile(
        r"[^@]+@[^@]+\.[^@]+"
    )  # Just basic sanity check for a @ and a dot
    if not EMAIL_REGEX.match(email_address):
        raise ImmediateHttpResponse(
            response=HttpResponse("Email is not valid", status=400)
        )
