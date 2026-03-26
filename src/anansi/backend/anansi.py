"""Controller for Anansi topology collection server.

Provides AnansiServer singleton that orchestrates server backend selection
and delegates to appropriate implementation (FastAPI or fallback).

Usage:
    ```python
    # Start server with defaults from config
    server = AnansiServer.get_instance()
    server.run_online()  # Uses config.server_config.host/port

    # Or override configuration
    server.run_online(addr="127.0.0.1", port=9000)

    # Run offline for fixed duration
    server.run_offline(duration=30.0)
    ```

Configuration (via config.json):
    ```json
    {
        "server_config": {
            "host": "0.0.0.0",
            "port": 18090,
            "preferred_backend": "FastAPIServer"
        }
    }
    ```

Architecture:
    - Uses ServerFactory to select backend based on preferred_backend config
    - Delegates all operations to backend implementation
    - Defaults to best available if preferred backend unavailable
    - Loads server settings from GlobalConfigManager

Dependencies:
    - fastapi/uvicorn: Optional, enables full REST API
    - Without dependencies: Fallback server supports offline mode only

Notes:
    Servers register automatically via lazy import in ServerFactory.
    preferred_backend=null in config enables auto-selection.
"""

from anansi.backend.base import Server, ServerFactory
from anansi.common.logging import get_logger
from anansi.common.singleton import ThreadSafeSingleton
from anansi.config_manager.config_manager import GlobalConfigManager
from anansi.controller.anansi_core import AnansiCore

LOGGER = get_logger(__name__)


class AnansiServer(ThreadSafeSingleton):
    """Singleton controller orchestrating backend server selection.

    Delegates to backend implementations (FastAPI or fallback) selected
    by ServerFactory based on available dependencies and configuration.

    Attributes:
        _core: AnansiCore singleton for topology collection
        _backend: Server implementation (FastAPIServer or OnlineDisabledServer)
        _config: Server configuration from GlobalConfigManager

    Notes:
        Automatically uses preferred backend from config, or auto-selects.
        Falls back to best available if preferred backend unavailable.
    """

    def __init__(self):
        self._core: AnansiCore = AnansiCore.get_instance()

        # Load server configuration
        config_mgr = GlobalConfigManager()
        self._config = config_mgr.get_config().server_config

        # Create backend based on configuration
        factory = ServerFactory()
        self._backend: Server = factory.create_server(
            server_type=self._config.preferred_backend, core=self._core
        )

        if self._backend is None:
            raise RuntimeError("No server backend available")

        LOGGER.info(f"Using backend: {self._backend.__class__.__name__}")
        if self._config.preferred_backend:
            LOGGER.info(
                f"Preferred backend from config: {self._config.preferred_backend}"
            )

    def run_offline(self, duration: float):
        """Run collection for fixed duration without HTTP server.

        Delegates to backend implementation.

        Args:
            duration: Collection duration in seconds
        """
        self._backend.run_offline(duration)

    def run_online(self, addr: str = None, port: int = None):
        """Start HTTP server and begin topology collection.

        Delegates to backend implementation. Blocks until shutdown.

        Args:
            addr: Server bind address (default from config)
            port: Server bind port (default from config)

        Raises:
            RuntimeError: If FastAPI unavailable (from OnlineDisabledServer)
        """
        # Use config defaults if not specified
        addr = addr or self._config.server_addr.host
        port = port or self._config.server_addr.port

        LOGGER.info(f"Starting server on {addr}:{port}")
        self._backend.run_online(addr, port)
