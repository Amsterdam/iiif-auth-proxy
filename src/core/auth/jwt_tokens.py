from datetime import datetime, timedelta, timezone

import jwt
from django.conf import settings
from django.http import HttpResponse
from jwt.exceptions import DecodeError, ExpiredSignatureError, InvalidSignatureError

from core.auth.constants import (
    RESPONSE_CONTENT_INVALID_SCOPE,
    RESPONSE_CONTENT_NO_TOKEN,
)
from main.utils import ImmediateHttpResponse


def check_auth_availability(request):
    if (
        not request.META.get("HTTP_AUTHORIZATION")
        and not request.GET.get("auth")
        and not settings.DATAPUNT_AUTHZ["ALWAYS_OK"]
    ):
        raise ImmediateHttpResponse(
            response=HttpResponse(RESPONSE_CONTENT_NO_TOKEN, status=401)
        )


def read_out_mail_jwt_token(request):
    jwt_token = {}
    is_mail_login = False
    if not request.META.get("HTTP_AUTHORIZATION"):
        if not request.GET.get("auth"):
            if settings.DATAPUNT_AUTHZ["ALWAYS_OK"]:
                return jwt_token, is_mail_login
            raise ImmediateHttpResponse(
                response=HttpResponse(RESPONSE_CONTENT_NO_TOKEN, status=401)
            )
        try:
            jwt_token = jwt.decode(
                request.GET.get("auth"),
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )
            # Check scopes
            for scope in jwt_token.get("scopes"):
                if scope not in (
                    settings.BOUWDOSSIER_PUBLIC_SCOPE,
                    settings.BOUWDOSSIER_READ_SCOPE,
                    settings.BOUWDOSSIER_EXTENDED_SCOPE,
                ):
                    raise ImmediateHttpResponse(
                        response=HttpResponse(
                            RESPONSE_CONTENT_INVALID_SCOPE, status=401
                        )
                    )
        except ExpiredSignatureError as e:
            raise ImmediateHttpResponse(
                response=HttpResponse("Expired JWT token signature", status=401)
            ) from e
        except InvalidSignatureError as e:
            raise ImmediateHttpResponse(
                response=HttpResponse("Invalid JWT token signature", status=401)
            ) from e
        except DecodeError as e:
            raise ImmediateHttpResponse(
                response=HttpResponse("Invalid JWT token", status=401)
            ) from e

        is_mail_login = True

    return jwt_token, is_mail_login


def create_mail_login_token(email_address, key, expiry_hours=24):
    """
    Prepare a JSON web token to be used by the dataportaal. A link which includes this token is sent to the
    citizens email address which in turn leads them to the dataportaal. This enables citizens to view images
    by sending along this token along with every file request.
    """
    exp = int((datetime.now(timezone.utc) + timedelta(hours=expiry_hours)).timestamp())
    jwt_payload = {
        "sub": email_address,
        "exp": exp,
        "scopes": [settings.BOUWDOSSIER_PUBLIC_SCOPE],
    }
    return jwt.encode(jwt_payload, key, algorithm=settings.JWT_ALGORITHM)
