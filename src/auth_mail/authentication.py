import logging
from datetime import datetime, timedelta

import jwt
from django.conf import settings
from django.http import HttpResponse
from jwt.exceptions import DecodeError, ExpiredSignatureError, InvalidSignatureError

from main.utils import ImmediateHttpResponse, find

log = logging.getLogger(__name__)

RESPONSE_CONTENT_NO_DOCUMENT_IN_METADATA = "Document not found in metadata"
RESPONSE_CONTENT_INVALID_SCOPE = "Invalid scope"
RESPONSE_CONTENT_NO_WABO_WITH_MAIL_LOGIN = (
    "WABO dossiers cannot be retrieved using the mail login access."
)
RESPONSE_CONTENT_RESTRICTED = "Document access is restricted"
RESPONSE_CONTENT_NO_TOKEN = "No token supplied"
RESPONSE_CONTENT_COPYRIGHT = "Document has copyright restriction"
RESPONSE_CONTENT_RESTRICTED_IN_ZIP = "Restricted documents cannot be requested in a zip"


class DocumentNotFoundInMetadataError(Exception):
    pass


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


def get_user_scope(request, mail_jwt_token):
    # request.get_token_scopes gets the authz or keycloak tokens.
    # mail_jwt_token['scopes'] get the in-url token which non-ambtenaren get in their email
    #
    # In case of an authz token a list is returned: https://github.com/Amsterdam/authorization_django/blob/97194d7a61deb25ac30ad2954bc913cc6ec28887/authorization_django/middleware.py#L159
    # but in case of a keycloak token a set is returned: https://github.com/Amsterdam/authorization_django/blob/97194d7a61deb25ac30ad2954bc913cc6ec28887/authorization_django/middleware.py#L166
    # So to not breaking adding a set with a list, below we always convert both structures to a set.

    request_token_scopes = set(getattr(request, "get_token_scopes", []))
    mail_jwt_scopes = set(mail_jwt_token.get("scopes", []))
    user_scopes = request_token_scopes | mail_jwt_scopes

    if (
        settings.DATAPUNT_AUTHZ["ALWAYS_OK"]
        or settings.BOUWDOSSIER_EXTENDED_SCOPE in user_scopes
    ):
        return settings.BOUWDOSSIER_EXTENDED_SCOPE

    if settings.BOUWDOSSIER_READ_SCOPE in user_scopes:
        return settings.BOUWDOSSIER_READ_SCOPE

    if settings.BOUWDOSSIER_PUBLIC_SCOPE in mail_jwt_scopes:
        return settings.BOUWDOSSIER_PUBLIC_SCOPE

    raise ImmediateHttpResponse(
        response=HttpResponse(RESPONSE_CONTENT_INVALID_SCOPE, status=401)
    )


def check_wabo_for_mail_login(is_mail_login, url_info):
    """
    This is a quick fix to stop citizens from viewing wabo files.
    """
    # TODO: replace this with a more sane check in which people who request mail login get a different scope
    if is_mail_login and url_info["source"] == "wabo":
        raise ImmediateHttpResponse(
            response=HttpResponse(RESPONSE_CONTENT_NO_WABO_WITH_MAIL_LOGIN, status=401)
        )


def check_file_access_in_metadata(metadata, url_info, scope):
    if scope not in (
        settings.BOUWDOSSIER_PUBLIC_SCOPE,
        settings.BOUWDOSSIER_EXTENDED_SCOPE,
        settings.BOUWDOSSIER_READ_SCOPE,
    ):
        raise ImmediateHttpResponse(
            response=HttpResponse(RESPONSE_CONTENT_INVALID_SCOPE, status=401)
        )
    # Check whether the image exists in the metadata
    try:
        is_public, has_copyright = img_is_public_copyright(
            metadata, url_info["document_barcode"]
        )
        if is_public:
            if scope == settings.BOUWDOSSIER_PUBLIC_SCOPE and has_copyright:
                raise ImmediateHttpResponse(
                    response=HttpResponse(RESPONSE_CONTENT_COPYRIGHT, status=401)
                )
        elif scope != settings.BOUWDOSSIER_EXTENDED_SCOPE:
            raise ImmediateHttpResponse(
                response=HttpResponse(RESPONSE_CONTENT_RESTRICTED, status=401)
            )
    except DocumentNotFoundInMetadataError as e:
        raise ImmediateHttpResponse(
            response=HttpResponse(RESPONSE_CONTENT_NO_DOCUMENT_IN_METADATA, status=404)
        ) from e


def is_caching_allowed(metadata, url_info):
    is_public, has_copyright = img_is_public_copyright(
        metadata, url_info["document_barcode"]
    )
    return is_public and not has_copyright


def check_restricted_file(metadata, url_info):
    is_public, _ = img_is_public_copyright(metadata, url_info["document_barcode"])
    if not is_public:
        raise ImmediateHttpResponse(
            response=HttpResponse(RESPONSE_CONTENT_RESTRICTED_IN_ZIP, status=400)
        )


def img_is_public_copyright(metadata, document_barcode):
    """
    Return whether document is public and has copyright.
    If the document is not public the copyright is not used and returned as unknown
    """
    is_public = False
    has_copyright = None
    if metadata["access"] != settings.ACCESS_PUBLIC:
        return is_public, has_copyright

    document = find(lambda d: d["barcode"] == document_barcode, metadata["documenten"])
    if not document:
        raise DocumentNotFoundInMetadataError()

    if document["access"] == settings.ACCESS_PUBLIC:
        is_public = True
        has_copyright = document.get("copyright") == settings.COPYRIGHT_YES

    return is_public, has_copyright


def create_mail_login_token(email_address, key, expiry_hours=24):
    """
    Prepare a JSON web token to be used by the dataportaal. A link which includes this token is sent to the
    citizens email address which in turn leads them to the dataportaal. This enables citizens to view images
    by sending along this token along with every file request.
    """
    exp = int((datetime.utcnow() + timedelta(hours=expiry_hours)).timestamp())
    jwt_payload = {
        "sub": email_address,
        "exp": exp,
        "scopes": [settings.BOUWDOSSIER_PUBLIC_SCOPE],
    }
    return jwt.encode(jwt_payload, key, algorithm=settings.JWT_ALGORITHM)
