import logging

from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from ratelimit.decorators import ratelimit

from iiif import tools

log = logging.getLogger(__name__)


@csrf_exempt
def index(request, iiif_url):
    try:
        tools.check_auth_availability(request)
        mail_jwt_token = tools.read_out_mail_jwt_token(request)
        scope = tools.get_max_scope(request, mail_jwt_token)
        url_info = tools.get_url_info(request, iiif_url)
        metadata = tools.get_metadata(url_info, iiif_url)
        tools.check_file_access_in_metadata(metadata, url_info, scope)
        file_response, file_url = tools.get_file(request.META, url_info, iiif_url, metadata)
        tools.handle_file_response_errors(file_response, file_url)
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
        tools.check_for_post(request)
        payload = tools.parse_payload(request)
        email, origin_url = tools.check_login_url_payload(payload)
        tools.check_email_validity(email)

        # Create the login url
        token = tools.create_mail_login_token(email, origin_url, settings.JWT_SECRET_KEY)
        login_url = f"{settings.DATAPORTAAL_LOGIN_BASE_URL}?auth={token}"

        # Send the email
        email_subject = "Toegang bouw- en omgevingsdossiers data.amsterdam.nl"
        # TODO: Maybe move email text to a template
        email_body = "Beste gebruiker van data.amsterdam.nl," \
                     "<br/><br/>Via onderstaande link bent u direct ingelogd op data.amsterdam.nl om de" \
                     "door u aangevraagde bouw- en omgevingsdossiers in te zien en te" \
                     "downloaden. Deze link is 24 uur geldig." \
                     f"<br/><br/><a clicktracking=off href='{login_url}'>Login dataportaal</a>" \
                     "<br/><br/>Met vriendelijke groet," \
                     "<br/><br/>Gemeente Amsterdam"

        # TODO: move actually sending the email to a separate process
        tools.send_email(payload['email'], email_subject, email_body)

    except tools.ImmediateHttpResponse as e:
        log.exception("ImmediateHttpResponse in login_url:")
        return e.response

    # Respond with a 200 to signal success.
    # The user will get an email asap with a login url
    return HttpResponse()


@csrf_exempt
def request_multiple_files_in_zip(request):
    try:
        tools.check_for_post(request)
        tools.check_auth_availability(request)
        read_jwt_token = tools.read_out_mail_jwt_token(request)
        scope = tools.get_max_scope(request, read_jwt_token)
        email_address = tools.get_email_address(request, read_jwt_token)
        payload = tools.parse_payload(request)
        tools.check_zip_payload(payload)
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
            iiif_url = tools.strip_full_iiif_url(url)
            url_info = tools.get_url_info(request, iiif_url)
            metadata = tools.get_metadata(url_info, iiif_url)
            tools.check_file_access_in_metadata(metadata, url_info, scope)
            # TODO: Get the file headers to check whether not only the metadata but also the source file itself exists
            #   Alternatively this can be handled when zipping the files

            # We create a new dict with all the info so that we have it when we want to get and zip the files later
            zip_info['urls'][iiif_url] = {
                'url_info': url_info,
                'metadata': metadata,
            }

        except tools.ImmediateHttpResponse as e:
            return e.response

    # The fact that we arrived here means that the the metadata exists for all files, and that the user is allowed to
    # access all the files. We proceed with storing it as a zip job so that a zip worker can pick it up.
    tools.store_zip_job(zip_info)

    # Respond with a 200 to signal success.
    # The user will get an email once the files have been zipped by a worker.
    return HttpResponse()
