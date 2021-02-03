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
        return e.response

    return HttpResponse(file_response.content, content_type=file_response.headers.get('Content-Type', ''))


# TODO: limit to dataportaal urls
@csrf_exempt
@ratelimit(key='ip', rate='3/d')  # TODO: Check django cache settings for rate limiter to work across paralel docker containers
def send_dataportaal_login_url_to_burger_email_address(request):
    try:
        # Some basic sanity checks
        tools.check_for_post(request)
        payload = tools.parse_payload(request)
        tools.check_login_url_payload(payload)
        tools.check_email_validity(payload['email'])

        # Create the login url
        token = tools.create_mail_login_token(payload['email'], settings.SECRET_KEY)
        login_url = f"{settings.DATAPORTAAL_LOGIN_BASE_URL}?auth={token}"

        # Send the email
        email_subject = "Amsterdam Dataportaal login"
        # TODO: Make better text and maybe an email template for this email
        email_body = f"Log in bij het Amsterdamse dataportaal met deze url: {login_url} " \
                     f"\nAls u deze email niet heeft aangevraagd dan hoeft u niets te doen."
        # TODO: move actually sending the email to a separate process
        tools.send_email(payload['email'], email_subject, email_body)

    except tools.ImmediateHttpResponse as e:
        return e.response

    # Respond with a 200 to signal success.
    # The user will get an email asap with a login url
    return HttpResponse()
