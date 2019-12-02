import time

from jwcrypto.jwt import JWT
from jwcrypto.jwk import JWKSet
from jwcrypto.common import JWException

from settings.settings import JWKS_TEST_KEY, EDEPOT_PUBLIC_SCOPE, EDEPOT_PRIVATE_SCOPE


_keyset = None


def load_jwks(jwks):
    global _keyset
    _keyset = JWKSet()
    try:
        _keyset.import_keyset(jwks)
    except JWException as e:
        raise Exception("Failed to import keyset from settings") from e
    print('Loaded JWKS from JWKS setting.')


def create_token():
    load_jwks(JWKS_TEST_KEY)
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
        'scopes': [EDEPOT_PUBLIC_SCOPE, EDEPOT_PRIVATE_SCOPE],
        'sub': 'testgas@amsterdam.nl',
    }
    token = JWT(
        header=header,
        claims=claims
    )
    token.make_signed_token(key)
    print(token.serialize())
    return token.serialize()