"""
Encryption utilities for storing credentials securely.
Uses Fernet symmetric encryption with a key stored in the user's config directory.
"""
import os
from pathlib import Path
from cryptography.fernet import Fernet

CONFIG_DIR = Path.home() / ".config" / "imap-sync-gui"
KEY_FILE = CONFIG_DIR / "secret.key"


def _get_or_create_key() -> bytes:
    """Load or generate the encryption key, storing it in the config directory."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if KEY_FILE.exists():
        return KEY_FILE.read_bytes()
    key = Fernet.generate_key()
    KEY_FILE.write_bytes(key)
    # Restrict permissions so only the owner can read/write
    KEY_FILE.chmod(0o600)
    return key


def _get_fernet() -> Fernet:
    return Fernet(_get_or_create_key())


def encrypt(plaintext: str) -> str:
    """Encrypt a plaintext string and return the ciphertext as a string."""
    if not plaintext:
        return ""
    return _get_fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(ciphertext: str) -> str:
    """Decrypt a ciphertext string and return the plaintext."""
    if not ciphertext:
        return ""
    try:
        return _get_fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except Exception:
        # If decryption fails (e.g. corrupted data), return empty string
        return ""
