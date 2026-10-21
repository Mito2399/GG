# app/crypto.py
#
# Authenticated symmetric encryption using Fernet (AES-128-CBC + HMAC-SHA256).
# Replaces the previous XOR-based scheme which was a two-time pad and therefore
# cryptographically broken (reusing the same keystream across values of the
# same field name leaked plaintext XOR relationships).
#
import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

logger = logging.getLogger(__name__)


def _derive_key(field_name: str) -> bytes:
    """
    Derive a Fernet key from SECRET_KEY + field_name.

    The field name is used as a salt so that the same plaintext encrypted
    under different field names produces different ciphertexts.
    """
    raw = hashlib.pbkdf2_hmac(
        hash_name  = "sha256",
        password   = settings.SECRET_KEY.encode("utf-8"),
        salt       = f"gg_fernet:{field_name}".encode("utf-8"),
        iterations = 200_000,
        dklen      = 32,
    )
    return base64.urlsafe_b64encode(raw)


def encrypt_value(field_name: str, plaintext: str) -> str:
    if not plaintext:
        return ""
    f = Fernet(_derive_key(field_name))
    return f.encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_value(field_name: str, ciphertext: str) -> str:
    if not ciphertext:
        return ""
    f = Fernet(_derive_key(field_name))
    try:
        return f.decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except InvalidToken:
        # Almost always: SECRET_KEY was rotated or the DB was copied from a
        # machine with a different SECRET_KEY. Rather than crash the app on
        # every login / settings page hit, log once and return "" so the
        # caller treats the secret as unset.
        logger.error(
            "[crypto] Cannot decrypt '%s' — SECRET_KEY changed. "
            "Re-enter this value in System Settings.", field_name,
        )
        return ""
    except Exception as exc:
        logger.error("[crypto] Decrypt error on '%s': %s", field_name, exc)
        return ""