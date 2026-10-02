"""
JSON storage backend with optional Fernet cryptographic encryption for disk inspection protection.
"""
import json
from pathlib import Path
import time
from typing import Any, Dict, Optional

from onion_search.storage.crypto import StorageEncryptor
from onion_search.utils.helpers import DEAD_FILE, STATE_FILE


class JSONBackend:
    """JSON file persistence backend with optional Fernet encryption."""

    def __init__(
        self,
        state_file: Path = STATE_FILE,
        dead_file: Path = DEAD_FILE,
        encrypt_storage: bool = False,
        encryptor: Optional[StorageEncryptor] = None,
    ) -> None:
        self.state_file = Path(state_file)
        self.dead_file = Path(dead_file)
        self.encrypt_storage = encrypt_storage
        self.encryptor = encryptor or (StorageEncryptor() if encrypt_storage else None)

    def load(self) -> Optional[Dict[str, Any]]:
        if not self.state_file.exists():
            return None
        try:
            with open(self.state_file, "rb") as f:
                raw = f.read()
            if self.encryptor:
                try:
                    return self.encryptor.decrypt_json(raw)
                except Exception:
                    pass
            # Fallback to plain JSON decoding
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return None

    def save(self, data: Dict[str, Any], incremental: bool = False) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        if self.encrypt_storage and self.encryptor:
            encrypted_data = self.encryptor.encrypt_json(data)
            with open(self.state_file, "wb") as f:
                f.write(encrypted_data)
        else:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

    def save_pending(self, pending: Dict[str, Any]) -> bool:
        return False

    def load_dead(self) -> Dict[str, float]:
        if not self.dead_file.exists():
            return {}
        try:
            with open(self.dead_file, "rb") as f:
                raw = f.read()
            if self.encryptor:
                try:
                    d = self.encryptor.decrypt_json(raw)
                except Exception:
                    d = json.loads(raw.decode("utf-8"))
            else:
                d = json.loads(raw.decode("utf-8"))
            now = time.time()
            return {u: t for u, t in d.items() if now - t < 24 * 3600}
        except Exception:
            return {}

    def save_dead(self, dead_dict: Dict[str, float]) -> None:
        try:
            self.dead_file.parent.mkdir(parents=True, exist_ok=True)
            if self.encrypt_storage and self.encryptor:
                encrypted = self.encryptor.encrypt_json(dead_dict)
                with open(self.dead_file, "wb") as f:
                    f.write(encrypted)
            else:
                with open(self.dead_file, "w", encoding="utf-8") as f:
                    json.dump(dead_dict, f)
        except Exception:
            pass

    def save_dead_pending(self, pending_dead: Dict[str, float]) -> None:
        self.save_dead(pending_dead)

    def clear(self) -> None:
        for p in [self.state_file, self.dead_file]:
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass
