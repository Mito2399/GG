import base64
import hashlib

from django.conf import settings


def _derive_key(field_name: str, length: int) -> bytes:

    return hashlib.pbkdf2_hmac(
        hash_name   = "sha256",
        password    = settings.SECRET_KEY.encode("utf-8"),
        salt        = f"gg_secret:{field_name}".encode("utf-8"),
        iterations  = 100_000,
        dklen       = length,
    )


def encrypt_value(field_name: str, plaintext: str) -> str:

    if not plaintext:
        return ""
    pt_bytes = plaintext.encode("utf-8")
    key      = _derive_key(field_name, len(pt_bytes))
    xored    = bytes(a ^ b for a, b in zip(pt_bytes, key))
    return base64.b64encode(xored).decode("ascii")


def decrypt_value(field_name: str, ciphertext: str) -> str:

    if not ciphertext:
        return ""
    ct_bytes = base64.b64decode(ciphertext.encode("ascii"))
    key      = _derive_key(field_name, len(ct_bytes))
    xored    = bytes(a ^ b for a, b in zip(ct_bytes, key))
    return xored.decode("utf-8")
