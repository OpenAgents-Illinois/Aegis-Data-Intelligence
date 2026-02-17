"""Connection string encryption/decryption using Fernet."""

from cryptography.fernet import Fernet, InvalidToken

from aegis.config import settings


def _get_fernet() -> Fernet:
    key = settings.encryption_key
    if not key:
        raise ValueError("AEGIS_ENCRYPTION_KEY is not configured")
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)


def encrypt(plaintext: str) -> str:
    """Encrypt a string and return base64-encoded ciphertext."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt a base64-encoded ciphertext string."""
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Failed to decrypt — invalid key or corrupted data") from exc


def generate_key() -> str:
    """Generate a new Fernet encryption key."""
    return Fernet.generate_key().decode()
