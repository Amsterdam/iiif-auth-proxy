import logging

from django.conf import settings
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from auth_mail import mailing
from core.auth.jwt_tokens import create_mail_login_token
from iiif import parsing
from main import utils

log = logging.getLogger(__name__)


# TODO: limit to dataportaal urls
@require_POST
@csrf_exempt
@ratelimit(
    key="ip", rate="3/d", block=False
)  # TODO: Check django cache settings for rate limiter to work across parallel docker containers
def send_dataportaal_login_url_to_mail(request):
    try:
        # Some basic sanity checks
        payload = parsing.parse_payload(request)
        email, origin_url = parsing.check_login_url_payload(payload)
        parsing.check_email_validity(email)

        # Create the login url
        token = create_mail_login_token(email, settings.JWT_SECRET_KEY)
        login_url = origin_url + "?auth=" + token

        # Send the email
        email_subject = "Toegang bouw- en omgevingsdossiers data.amsterdam.nl"
        email_body = render_to_string("login_link.html", {"login_url": login_url})
        # TODO: move actually sending the email to a separate process
        mailing.send_email(payload["email"], email_subject, email_body)

    except utils.ImmediateHttpResponse as e:
        log.exception("ImmediateHttpResponse in login_url:")
        return e.response

    # Respond with a 200 to signal success.
    # The user will get an email asap with a login url
    return HttpResponse()
