"""Global configuration management for Anansi framework.

Provides centralized configuration management for all collectors and sniffers.
Loads from JSON files or programmatic defaults, and exposes configurations
via GlobalConfigManager singleton.

Key Components:
    - GlobalConfig: Dataclass aggregating all configuration sections
    - GlobalConfigManager: Singleton providing thread-safe config access
    - SnifferConfig: Configuration for all data source sniffers
    - CollectorConfig: Configuration for topology collectors

GlobalConfig Sections:
    - tmp_dir: Temporary directory for sniffer data files
    - sniffer_config: Socket/IPC/memory sniffer configurations
    - collector_config: Collector-specific settings (start nodes, enabled collectors)
    - server_config: HTTP server binding and backend selection preferences

Usage:
    ```python
    # Get global configuration
    config_mgr = GlobalConfigManager.get_instance()
    global_config = config_mgr.global_config
    print(f"Server config: {global_config.server_config}")

    # Load from file
    config_mgr = GlobalConfigManager.get_instance()
    config_mgr.load_config_from_json_file("config.json")

    # Access server config
    server_config = global_config.server_config
    ```

Configuration File Format (JSON):
    ```json
    {
        "tmp_dir": "local/run/anansi",
        "sniffer_config": {...},
        "collector_config": {...},
        "server_config": {
            "host": "0.0.0.0",
            "port": 18090,
            "preferred_backend": "FastAPIServer"
        }
    }
    ```

Notes:
    Singleton pattern ensures all modules use consistent configuration.
    Configuration is loaded once during first get_instance() call.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict

from anansi.common.logging import get_logger
from anansi.common.singleton import Singleton
from anansi.config_manager.configs import GlobalConfig

LOGGER = get_logger(__name__)


class GlobalConfigManager(Singleton):
    """Singleton class to manage global configuration."""

    _config = None

    def __init__(self, config: dict | str = None):
        if self._config is not None:
            raise RuntimeError("GlobalConfigManager is a singleton class.")
        config_abbr = (
            "config dict"
            if isinstance(config, dict)
            else (config if isinstance(config, str) else "None")
        )
        LOGGER.info(
            "Initializing GlobalConfigManager(id %s) with config: %s",
            id(self),
            config_abbr,
        )

        self._config = GlobalConfig(**self._load_config(config))
        LOGGER.debug("GlobalConfigManager initialized (id %s)", id(self))
        self.clean_up_temp_dir()  # Ensure temp dir is clean on startup

    def _load_config(self, config: dict | str | None) -> dict:
        if config is None:
            return {}
        elif isinstance(config, str):
            with open(config, "r") as f:
                return json.load(f)
        else:
            return config

    def clean_up_temp_dir(self):
        """Clean up the temporary directory."""
        import shutil

        shutil.rmtree(self._config.tmp_dir, ignore_errors=True)

    def get_config(self) -> GlobalConfig:
        """Get the global configuration."""
        return self._config

    def convert_to_tmp_path(self, path: str) -> str:
        """Convert a given path to a temporary directory path."""
        import os

        if os.path.isabs(path):
            return path
        if os.path.isabs(self._config.tmp_dir):
            return os.path.join(self._config.tmp_dir, path)

        return os.path.join(os.path.dirname("."), self._config.tmp_dir, path)

    def dump_config(self, path: str):
        """Dump the current configuration to a file."""

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(asdict(self._config), f, indent=4)
        LOGGER.info("Configuration dumped to %s", path)


__all__ = ["GlobalConfigManager"]


if __name__ == "__main__":
    config_manager = GlobalConfigManager()
    config_manager.dump_config(
        os.path.join(os.path.dirname(__file__), "..", "config", "config.json")
    )
