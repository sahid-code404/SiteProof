from app.core.security import create_access_token, decode_access_token, hash_password, verify_password


def test_password_hash_roundtrip():
    password = "CorrectHorseBatteryStaple!42"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("wrong-password", hashed)


def test_jwt_roundtrip():
    token = create_access_token("abc", {"role": "ADMIN"})
    payload = decode_access_token(token)
    assert payload["sub"] == "abc"
    assert payload["role"] == "ADMIN"
