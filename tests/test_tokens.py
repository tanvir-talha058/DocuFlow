from app.services.tokens import generate_token, hash_token


def test_generate_token_hash_matches():
    raw, token_hash, expires_at = generate_token()
    assert hash_token(raw) == token_hash


def test_different_tokens_have_different_hashes():
    raw1, hash1, _ = generate_token()
    raw2, hash2, _ = generate_token()
    assert raw1 != raw2
    assert hash1 != hash2


def test_token_expiry_is_in_the_future():
    from datetime import datetime

    _, _, expires_at = generate_token()
    assert expires_at > datetime.utcnow()
