# Copyright 2026 HES Projects by FePe
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Cryptographic encryption layer using cryptography.fernet.Fernet for storage privacy.
Protects stored visited onion URLs and dead blacklists against offline disk inspection.
Developed by HES Projects by FePe.
"""
import base64
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Optional, Tuple, Union
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from onion_search.config import CONFIG_DIR

logger = logging.getLogger("onion_search")

DEFAULT_KEY_FILE = CONFIG_DIR / ".storage.key"


class StorageEncryptor:
    """Handles symmetric Fernet encryption/decryption for persistent files."""

    def __init__(self, key: Optional[Union[str, bytes]] = None, key_file: Path = DEFAULT_KEY_FILE) -> None:
        self.key_file = key_file
        self.salt_file = self.key_file.parent / ".storage.salt"
        self._raw_passphrase_bytes: Optional[bytes] = None
        self.key = self._resolve_key(key)
        self.fernet = Fernet(self.key)

    def _get_or_create_salt(self) -> bytes:
        if self.salt_file.exists():
            try:
                st = os.stat(self.salt_file)
                mode = st.st_mode & 0o777
                if mode != 0o600:
                    try:
                        os.chmod(self.salt_file, 0o600)
                    except Exception:
                        pass
            except Exception:
                pass

            try:
                with open(self.salt_file, "rb") as f:
                    s = f.read()
                if len(s) == 16:
                    return s
            except Exception:
                pass

        salt = os.urandom(16)
        try:
            self.salt_file.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.chmod(self.salt_file.parent, 0o700)
            except Exception:
                pass
            fd = os.open(self.salt_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(salt)
            try:
                os.chmod(self.salt_file, 0o600)
            except Exception:
                pass
        except Exception:
            pass
        return salt

    def _derive_pbkdf2_key(self, passphrase_bytes: bytes, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=600_000,
        )
        return base64.urlsafe_b64encode(kdf.derive(passphrase_bytes))

    def _resolve_key(self, key: Optional[Union[str, bytes]]) -> bytes:
        if key:
            if isinstance(key, str):
                key_bytes = key.encode("utf-8")
            else:
                key_bytes = key
            if len(key_bytes) != 44 or not key_bytes.endswith(b"="):
                self._raw_passphrase_bytes = key_bytes
                salt = self._get_or_create_salt()
                return self._derive_pbkdf2_key(key_bytes, salt)
            return key_bytes

        # If keyfile exists, check permissions and load it
        if self.key_file.exists():
            try:
                st = os.stat(self.key_file)
                mode = st.st_mode & 0o777
                if mode != 0o600:
                    try:
                        os.chmod(self.key_file, 0o600)
                        logger.warning(
                            f"[SECURITY] Key file permissions were too permissive ({oct(mode)}), tightened to 0o600: {self.key_file}"
                        )
                    except Exception:
                        pass
            except Exception:
                pass

            try:
                with open(self.key_file, "rb") as f:
                    saved_key = f.read().strip()
                if len(saved_key) == 44:
                    return saved_key
            except Exception:
                pass

        # Ensure parent directory has 0o700 permissions
        try:
            self.key_file.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.chmod(self.key_file.parent, 0o700)
            except Exception:
                pass
        except Exception:
            pass

        # Generate a new random Fernet key and save with O_CREAT | O_EXCL | O_WRONLY and 0o600 mode
        new_key = Fernet.generate_key()
        try:
            fd = os.open(
                self.key_file,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
            with os.fdopen(fd, "wb") as f:
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
        """Decrypt ciphertext bytes back to plaintext with fallback to legacy SHA-256 derived key."""
        try:
            return self.fernet.decrypt(token)
        except InvalidToken:
            if self._raw_passphrase_bytes:
                legacy_derived = base64.urlsafe_b64encode(hashlib.sha256(self._raw_passphrase_bytes).digest())
                legacy_fernet = Fernet(legacy_derived)
                try:
                    plaintext = legacy_fernet.decrypt(token)
                    logger.warning("[SECURITY] régi kulcsformátum, újratitkosítás javasolt")
                    return plaintext
                except InvalidToken:
                    pass
            raise

    def encrypt_json(self, data: Any) -> bytes:
        """Serialize data to JSON and return encrypted ciphertext bytes."""
        serialized = json.dumps(data, ensure_ascii=False).encode("utf-8")
        return self.encrypt_bytes(serialized)

    def decrypt_json(self, token: bytes) -> Any:
        """Decrypt ciphertext and parse decrypted JSON payload."""
        plaintext = self.decrypt_bytes(token)
        return json.loads(plaintext.decode("utf-8"))
