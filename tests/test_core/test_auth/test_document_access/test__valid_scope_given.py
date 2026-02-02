import pytest
from django.conf import settings

from core.auth.document_access import _valid_scope_given
from main.utils import ImmediateHttpResponse


@pytest.mark.parametrize(
    "valid_scope",
    [
        settings.BOUWDOSSIER_PUBLIC_SCOPE,
        settings.BOUWDOSSIER_EXTENDED_SCOPE,
        settings.BOUWDOSSIER_READ_SCOPE,
    ],
)
def test_valid_scopes_pass(valid_scope):
    """Valid scopes should not raise"""
    _valid_scope_given(valid_scope)


@pytest.mark.parametrize(
    "invalid_scope",
    [
        "INVALID_SCOPE",
        "",
        None,
    ],
)
def test_invalid_scopes_raise(invalid_scope):
    """Invalid scopes should raise ImmediateHttpResponse"""
    with pytest.raises(ImmediateHttpResponse):
        _valid_scope_given(invalid_scope)
