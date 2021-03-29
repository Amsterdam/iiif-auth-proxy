import logging

import sendgrid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from sendgrid.helpers.mail import Mail

log = logging.getLogger(__name__)


def send_email(email_address, email_subject, email_body):
    if not settings.SENDGRID_KEY:
        log.error("No SENDGRID_KEY found. Not sending emails.")
        return
    try:
        validate_email(email_address)
    except ValidationError:
        log.error("No valid email address. Not sending email.")
        return

    sg = sendgrid.SendGridAPIClient(settings.SENDGRID_KEY)
    email = Mail(
        from_email='noreply@amsterdam.nl',
        to_emails=[email_address],
        subject=email_subject,
        html_content=email_body
    )
    sg.send(email)
