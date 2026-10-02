"""
Configuration management and constants for Onion Kereso.
Persists application settings to ~/.config/onion_search/config.json.
"""
from dataclasses import asdict, dataclass
import json
import logging
from pathlib import Path
from typing import Any, Dict

# Central storage directories
CONFIG_DIR = Path.home() / ".config" / "onion_search"
CONFIG_FILE = CONFIG_DIR / "config.json"
STATE_DIR = CONFIG_DIR
DB_FILE = STATE_DIR / "onion.db"
DEFAULT_STATE_FILE = STATE_DIR / "state_v3.json"
DEFAULT_DEAD_FILE = STATE_DIR / "dead_blacklist.json"

# Network & Scraping Constants (eliminating magic numbers)
DEFAULT_TIMEOUT_GET: int = 20
TIMEOUT_GET: int = DEFAULT_TIMEOUT_GET
MIN_HTML_BODY_LENGTH: int = 300
MIN_TEXT_CONTENT_LENGTH: int = 200
MAX_CONTENT_TEXT_LENGTH: int = 8000
USER_AGENT_ROTATE_PROBABILITY: float = 0.3
MIN_NEWNYM_INTERVAL_AUTO: float = 12.0
MIN_NEWNYM_INTERVAL_TRIGGER: float = 15.0
DEFAULT_DOMAIN_DELAY: float = 1.0
DEFAULT_MAX_RETRIES: int = 2
MAX_MEMORY_CACHE_SIZE: int = 50000

# Tor Network Ports & Defaults
DEFAULT_SOCKS_PORT: str = "9050"
DEFAULT_CTRL_PORT: str = "9051"
DEFAULT_WORKERS: int = 6
DEFAULT_BACKEND: str = "sqlite"

# Auto-NEWNYM thresholds
DEFAULT_SUCCESS_THRESHOLD: int = 50
DEFAULT_TOTAL_THRESHOLD: int = 100


@dataclass
class AppConfig:
    """Strongly typed application configuration settings."""

    socks_port: str = DEFAULT_SOCKS_PORT
    ctrl_port: str = DEFAULT_CTRL_PORT
    workers: int = DEFAULT_WORKERS
    backend: str = DEFAULT_BACKEND
    dark_mode: bool = True
    auto_newnym_success: bool = True
    auto_newnym_total: bool = True
    success_threshold: int = DEFAULT_SUCCESS_THRESHOLD
    total_threshold: int = DEFAULT_TOTAL_THRESHOLD
    auto_save: bool = True
    live_filtering: bool = True
    allow_clearnet: bool = False
    encrypt_storage: bool = False
    timeout_get: int = DEFAULT_TIMEOUT_GET
    domain_delay: float = DEFAULT_DOMAIN_DELAY
    queries: str = "forum, board, wiki, library"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        valid_keys = cls.__dataclass_fields__.keys()
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ConfigManager:
    """Loads and persists AppConfig to ~/.config/onion_search/config.json."""

    def __init__(self, config_file: Path = CONFIG_FILE) -> None:
        self.config_file = config_file
        self.config = self.load()

    def load(self) -> AppConfig:
        """Load configuration from JSON file or create with defaults."""
        try:
            if self.config_file.exists():
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return AppConfig.from_dict(data)
        except Exception as e:
            logging.getLogger("onion_search").warning(f"Config betöltési hiba: {e}")
        return AppConfig()

    def save(self, config: AppConfig = None) -> bool:
        """Save configuration settings to JSON file."""
        if config is not None:
            self.config = config
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config.to_dict(), f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logging.getLogger("onion_search").error(f"Config mentési hiba: {e}")
            return False
