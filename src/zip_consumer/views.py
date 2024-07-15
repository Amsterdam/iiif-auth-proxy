import json
import logging
import uuid

from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from auth_mail import authentication
from iiif import parsing
from main import utils
from main.utils_azure_storage import store_blob_on_storage_account
from zip_consumer import zip_tools

log = logging.getLogger(__name__)


@csrf_exempt
def request_multiple_files_in_zip(request):
    try:
        parsing.check_for_post(request)
        authentication.check_auth_availability(request)
        read_jwt_token, is_mail_login = authentication.read_out_mail_jwt_token(request)
        scope = authentication.get_user_scope(request, read_jwt_token)
        email_address = parsing.get_email_address(request, read_jwt_token)
        payload = parsing.parse_payload(request)
        parsing.check_zip_payload(payload)
    except utils.ImmediateHttpResponse as e:
        log.error(e.response.content)
        return e.response

    zip_info = {
        "email_address": email_address,
        "request_meta": request.META,
        "urls": {},
        "scope": scope,
        "is_mail_login": is_mail_login,
    }
    for full_url in payload["urls"]:
        try:
            iiif_url = parsing.strip_full_iiif_url(full_url)
            url_info = parsing.get_url_info(iiif_url, True)
            authentication.check_wabo_for_mail_login(is_mail_login, url_info)

            # We create a new dict with all the info so that we have it when we want to get and zip the files later
            zip_info["urls"][iiif_url] = {"url_info": url_info}

        except utils.ImmediateHttpResponse as e:
            log.error(e.response.content)
            return e.response

    # The fact that we arrived here means that urls are formatted correctly and the info is extracted from it.
    # It does NOT mean that the metadata exists or that the user is allowed to access all the files. This will
    # be checked in the consumer. We now proceed with storing the info as a zip job so that a zip worker
    # can pick it up.

    # Zip_info is too large for the request body (hard limit by Azure). So we use the claim check pattern.
    # First, the jobs/zip_info is stored as a blob in the storage_account. Then we send a reference to the blob to the queue
    blob_name = str(uuid.uuid4())
    zip_job = json.dumps(
        {
            key: zip_info[key]
            for key in ["email_address", "scope", "is_mail_login", "urls"]
        }
    )
    store_blob_on_storage_account(
        settings.STORAGE_ACCOUNT_CONTAINER_ZIP_QUEUE_JOBS_NAME, blob_name, zip_job
    )
    zip_tools.store_zip_job(blob_name)

    # Respond with a 200 to signal success.
    # The user will get an email once the files have been zipped by a worker.
    return HttpResponse()
