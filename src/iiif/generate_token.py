import time

from django.conf import settings
from jwcrypto.common import JWException
from jwcrypto.jwk import JWKSet
from jwcrypto.jwt import JWT

_keyset = None


def load_jwks(jwks):
    global _keyset
    _keyset = JWKSet()
    try:
        _keyset.import_keyset(jwks)
    except JWException as e:
        raise Exception("Failed to import keyset from settings") from e


def create_authz_token(scopes=None):
    if scopes is None:
        scopes = []
    if type(scopes) not in (list, tuple, set):
        scopes = [scopes]

    load_jwks(settings.JWKS_TEST_KEY)
    key = next(iter(_keyset['keys']))
    now = int(time.time())
    header = {
        'alg': 'ES256',
        'kid': key.key_id
        # 'kid': 'abcd5678'
    }
    claims = {
        'iat': now,
        'exp': now + 3600,
        'scopes': scopes,
        'sub': 'authztest@amsterdam.nl',
    }
    token = JWT(
        header=header,
        claims=claims
    )
    token.make_signed_token(key)
    return token.serialize()
