"""
Cryptographic encryption layer using cryptography.fernet.Fernet for storage privacy.
Protects stored visited onion URLs and dead blacklists against offline disk inspection.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Optional, Tuple, Union
from cryptography.fernet import Fernet, InvalidToken

from onion_search.config import CONFIG_DIR

DEFAULT_KEY_FILE = CONFIG_DIR / ".storage.key"


class StorageEncryptor:
    """Handles symmetric Fernet encryption/decryption for persistent files."""

    def __init__(self, key: Optional[Union[str, bytes]] = None, key_file: Path = DEFAULT_KEY_FILE) -> None:
        self.key_file = key_file
        self.key = self._resolve_key(key)
        self.fernet = Fernet(self.key)

    def _resolve_key(self, key: Optional[Union[str, bytes]]) -> bytes:
        if key:
            if isinstance(key, str):
                key_bytes = key.encode("utf-8")
            else:
                key_bytes = key
            # If user provided a password/passphrase rather than 32-byte urlsafe base64, derive key via sha256
            if len(key_bytes) != 44 or not key_bytes.endswith(b"="):
                derived = hashlib.sha256(key_bytes).digest()
                return base64.urlsafe_b64encode(derived)
            return key_bytes

        # If keyfile exists, load it
        if self.key_file.exists():
            try:
                with open(self.key_file, "rb") as f:
                    saved_key = f.read().strip()
                if len(saved_key) == 44:
                    return saved_key
            except Exception:
                pass

        # Generate a new random Fernet key and save with restricted permissions
        new_key = Fernet.generate_key()
        try:
            self.key_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.key_file, "wb") as f:
                f.write(new_key)
            try:
                os.chmod(self.key_file, 0o600)
            except Exception:
                pass
        except Exception:
            pass
        return new_key

    def encrypt_bytes(self, data: bytes) -> bytes:
        """Encrypt raw bytes using Fernet."""
        return self.fernet.encrypt(data)

    def decrypt_bytes(self, token: bytes) -> bytes:
        """Decrypt ciphertext bytes back to plaintext."""
        return self.fernet.decrypt(token)

    def encrypt_json(self, data: Any) -> bytes:
        """Serialize data to JSON and return encrypted ciphertext bytes."""
        serialized = json.dumps(data, ensure_ascii=False).encode("utf-8")
        return self.encrypt_bytes(serialized)

    def decrypt_json(self, token: bytes) -> Any:
        """Decrypt ciphertext and parse decrypted JSON payload."""
        plaintext = self.decrypt_bytes(token)
        return json.loads(plaintext.decode("utf-8"))
