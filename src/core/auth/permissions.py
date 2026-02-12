from django.conf import settings
from django.http import HttpResponse

from core.auth.constants import (
    RESPONSE_CONTENT_INVALID_SCOPE,
    RESPONSE_CONTENT_NO_WABO_WITH_MAIL_LOGIN,
)
from main.utils import ImmediateHttpResponse


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

    if settings.DATAPUNT_AUTHZ["ALWAYS_OK"] or settings.BOUWDOSSIER_EXTENDED_SCOPE in user_scopes:
        return settings.BOUWDOSSIER_EXTENDED_SCOPE

    if settings.BOUWDOSSIER_READ_SCOPE in user_scopes:
        return settings.BOUWDOSSIER_READ_SCOPE

    if settings.BOUWDOSSIER_PUBLIC_SCOPE in mail_jwt_scopes:
        return settings.BOUWDOSSIER_PUBLIC_SCOPE

    raise ImmediateHttpResponse(response=HttpResponse(RESPONSE_CONTENT_INVALID_SCOPE, status=401))


def check_wabo_for_mail_login(is_mail_login, url_info):
    """
    This is a quick fix to stop citizens from viewing wabo files.
    """
    # TODO: replace this with a more sane check in which people who request mail login get a different scope
    if is_mail_login and url_info["source"] == "wabo":
        raise ImmediateHttpResponse(response=HttpResponse(RESPONSE_CONTENT_NO_WABO_WITH_MAIL_LOGIN, status=401))
