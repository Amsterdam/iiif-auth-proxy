import logging

from sentry_sdk import capture_message

log = logging.getLogger(__name__)


class SimpleMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        log.critical("IN THE MIDDLEWARE log")
        capture_message("IN THE MIDDLEWARE sentry")
        

        response = self.get_response(request)
        return response
