import json
import logging

from django.conf import settings
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt
from ingress.models import Collection, Message
from ratelimit.decorators import ratelimit

from iiif import authentication, cantaloupe, mailing, parsing, tools, zip_tools
from iiif.metadata import get_metadata

log = logging.getLogger(__name__)


@csrf_exempt
def index(request, iiif_url):
    try:
        authentication.check_auth_availability(request)
        mail_jwt_token = authentication.read_out_mail_jwt_token(request)
        scope = authentication.get_max_scope(request, mail_jwt_token)
        url_info = parsing.get_url_info(request, iiif_url)
        metadata = get_metadata(url_info, iiif_url)
        authentication.check_file_access_in_metadata(metadata, url_info, scope)
        file_response, file_url = cantaloupe.get_file(request.META, url_info, iiif_url, metadata)
        cantaloupe.handle_file_response_errors(file_response, file_url)
    except tools.ImmediateHttpResponse as e:
        log.exception("ImmediateHttpResponse in index:")
        return e.response

    return HttpResponse(file_response.content, content_type=file_response.headers.get('Content-Type', ''))


# TODO: limit to dataportaal urls
@csrf_exempt
@ratelimit(key='ip', rate='3/d')  # TODO: Check django cache settings for rate limiter to work across parallel docker containers
def send_dataportaal_login_url_to_mail(request):
    try:
        # Some basic sanity checks
        parsing.check_for_post(request)
        payload = parsing.parse_payload(request)
        email, origin_url = parsing.check_login_url_payload(payload)
        parsing.check_email_validity(email)

        # Create the login url
        token = authentication.create_mail_login_token(email, settings.JWT_SECRET_KEY)
        login_url = origin_url + '?auth=' + token

        # Store a job to send the email
        email_info = {
            'email': payload['email'],
            'subject': "Toegang bouw- en omgevingsdossiers data.amsterdam.nl",
            'body': render_to_string('login_link.html', {'login_url': login_url}),
        }
        collection = Collection.objects.get(name=settings.EMAIL_COLLECTION_NAME)
        Message.objects.create(
            raw_data=json.dumps(email_info),
            collection=collection
        )

    except tools.ImmediateHttpResponse as e:
        log.exception("ImmediateHttpResponse in login_url:")
        return e.response

    # Respond with a 200 to signal success.
    # The user will get an email asap with a login url
    return HttpResponse()


@csrf_exempt
def request_multiple_files_in_zip(request):
    try:
        parsing.check_for_post(request)
        authentication.check_auth_availability(request)
        read_jwt_token = authentication.read_out_mail_jwt_token(request)
        scope = authentication.get_max_scope(request, read_jwt_token)
        email_address = parsing.get_email_address(request, read_jwt_token)
        payload = parsing.parse_payload(request)
        parsing.check_zip_payload(payload)
    except tools.ImmediateHttpResponse as e:
        log.error(e.response.content)
        return e.response

    zip_info = {
        'email_address': email_address,
        'request_meta': request.META,
        'urls': {}
    }
    for url in payload['urls']:
        try:
            iiif_url = parsing.strip_full_iiif_url(url)
            url_info = parsing.get_url_info(request, iiif_url)
            metadata = get_metadata(url_info, iiif_url)
            authentication.check_file_access_in_metadata(metadata, url_info, scope)
            authentication.check_restricted_file(metadata, url_info)
            # TODO: Get the file headers to check whether not only the metadata but also the source file itself exists
            #   Alternatively this can be handled when zipping the files

            # We create a new dict with all the info so that we have it when we want to get and zip the files later
            zip_info['urls'][iiif_url] = {
                'url_info': url_info,
                'metadata': metadata,
            }

        except tools.ImmediateHttpResponse as e:
            log.error(e.response.content)
            return e.response

    # The fact that we arrived here means that the the metadata exists for all files, and that the user is allowed to
    # access all the files. We proceed with storing it as a zip job so that a zip worker can pick it up.
    zip_tools.store_zip_job(zip_info)

    # Respond with a 200 to signal success.
    # The user will get an email once the files have been zipped by a worker.
    return HttpResponse()
