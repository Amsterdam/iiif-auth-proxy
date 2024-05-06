import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.utils.html import strip_tags

log = logging.getLogger(__name__)


def send_email(email_address, email_subject, email_body):
    if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
        log.error("No EMAIL_HOST_USER found. Not sending emails.")
        return

    try:
        validate_email(email_address)
    except ValidationError:
        # TODO: In case this email is sent from within a request, it should throw an error so that we can serve
        #  the error back to the user
        log.error("No valid email address. Not sending email.")
        return

    send_mail(
        email_subject,
        strip_tags(email_body),
        settings.EMAIL_FROM_EMAIL_ADDRESS,
        [email_address],
        html_message=email_body,
        fail_silently=False,
    )
