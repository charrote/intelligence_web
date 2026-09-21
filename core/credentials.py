"""Credential encryption for datasource auth (auth_type basic/bearer/cookie/form_login).

Secrets are stored as Fernet tokens (AES-128-CBC + HMAC-SHA256) in the DB.
The key is derived from the CREDENTIALS_ENCRYPT_KEY environment variable via
PBKDF2-HMAC-SHA256. There is NO hardcoded default: without the env var,
encryption/decryption is refused (see CredentialKeyMissingError).

Env var value may be any passphrase; it is stretched with PBKDF2
(200_000 iterations, application-fixed salt) into a 32-byte Fernet key.
"""

import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken

_SALT = b"intelligence-web-datasource-credential-v1"
_ITERATIONS = 200_000


class CredentialKeyMissingError(Exception):
    """Raised when CREDENTIALS_ENCRYPT_KEY is not configured."""


def _get_fernet() -> Fernet:
    """Build the Fernet instance from the env-var key.

    Raises CredentialKeyMissingError if the env var is absent or empty.
    """
    passphrase = os.environ.get("CREDENTIALS_ENCRYPT_KEY", "")
    if not passphrase:
        raise CredentialKeyMissingError(
            "CREDENTIALS_ENCRYPT_KEY 未配置，无法保存/读取数据源凭证"
        )
    key = hashlib.pbkdf2_hmac(
        "sha256", passphrase.encode("utf-8"), _SALT, _ITERATIONS
    )
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a plaintext secret to a storable Fernet token (ascii).

    Raises CredentialKeyMissingError when no key is configured.
    """
    if not plaintext:
        return ""
    return _get_fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_secret(token: str) -> str:
    """Decrypt a Fernet token to plaintext.

    Returns "" for empty tokens or when the token cannot be decrypted
    (wrong key / corrupted / legacy value) — callers treat "" as
    "credential unavailable" and fall back to unauthenticated behavior.
    """
    if not token:
        return ""
    try:
        return _get_fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, CredentialKeyMissingError):
        return ""
