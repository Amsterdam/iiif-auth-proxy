import logging

from django.http import HttpResponse

log = logging.getLogger(__name__)


class ImmediateHttpResponse(Exception):
    """
    This exception is used to interrupt the flow of processing to immediately
    return a custom HttpResponse.
    """

    _response = HttpResponse("Nothing provided.")

    def __init__(self, response):
        self._response = response

    @property
    def response(self):
        return self._response


def str_to_bool(boolstr):
    if not isinstance(boolstr, str):
        return False
    return boolstr.lower() in ("1", "t", "true")
