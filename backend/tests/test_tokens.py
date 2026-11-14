import jwt
import pytest
from jwt.exceptions import InvalidTokenError


def test_access_token_has_expected_claims(token_context):
    token = token_context.valid_token
    secret = token_context.secret
    expected_subject = str(token_context.user_id)
    expected_algorithm = "HS256"
    expected_lifetime = 1800
    required_claims = {"sub", "iat", "exp"}

    payload = jwt.decode(token, secret, algorithms=[expected_algorithm])
    for claim in required_claims:
        assert claim in payload
    assert payload["sub"] == expected_subject
    assert type(payload["iat"]) is int
    assert type(payload["exp"]) is int
    assert payload["exp"] - payload["iat"] == expected_lifetime
    assert (
        token_context.creation_started_at <=
        payload["iat"] <=
        token_context.creation_finished_at
    )
    header = jwt.get_unverified_header(token)

    assert header["alg"] == expected_algorithm


@pytest.mark.parametrize("time_case", ["expired", "future-issued"])
def test_decode_rejects_invalid_token_times(token_context, time_case):
    claims = token_context.claims.copy()
    secret = token_context.secret
    algorithm = "HS256"
    now = token_context.creation_started_at

    if time_case == "expired":
        claims["exp"] = now - 1800
        claims["iat"] = now - 3600
    elif time_case == "future-issued":
        claims["exp"] = now + 2100
        claims["iat"] = now + 300

    token = jwt.encode(claims, secret, algorithm=algorithm)

    with pytest.raises(InvalidTokenError):
        token_context.tokens.decode_access_token(token)

@pytest.mark.parametrize(
    "invalid_case",
    ["wrong-key", "wrong-algorithm", "missing-sub", "missing-iat", "missing-exp"],
)
def test_decode_rejects_invalid_token_credentials(token_context, invalid_case):
    claims = token_context.claims.copy()
    signing_key = token_context.secret
    algorithm = "HS256"

    if invalid_case == "wrong-key":
        signing_key = token_context.secret + "-other"
    elif invalid_case == "wrong-algorithm":
        algorithm = "HS384"
    else:
        missing_claim = invalid_case.removeprefix("missing-")
        del claims[missing_claim]

    token = jwt.encode(claims, signing_key, algorithm=algorithm)

    with pytest.raises(InvalidTokenError):
        token_context.tokens.decode_access_token(token)