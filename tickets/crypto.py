"""Fernet encryption for IMAP/SMTP passwords stored in DB."""
import os

from cryptography.fernet import Fernet

_KEY_ENV = "TICKET_ENCRYPTION_KEY"


def _get_fernet() -> Fernet:
    key = os.environ.get(_KEY_ENV)
    if not key:
        raise RuntimeError(
            f"Environment variable {_KEY_ENV} is not set. "
            "Generate one with: python3 -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode())


def encrypt_value(plaintext: str) -> str:
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    return _get_fernet().decrypt(ciphertext.encode()).decode()
