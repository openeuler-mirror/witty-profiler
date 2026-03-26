"""Base server interface and registry for Witty Profiler HTTP backends.

Defines Server ABC with metaclass-based auto-registration, similar to
Entity/Collector patterns. Concrete servers register automatically on
import, enabling factory-based instantiation.

Key Components:
    - Server: Abstract base class for all server implementations
    - ServerMeta: Metaclass for automatic server type registration
    - ServerFactory: Singleton factory for server instantiation

Server Lifecycle:
    1. Subclass Server and implement abstract methods
    2. Server auto-registers via ServerMeta on import
    3. Factory creates instances based on available servers
    4. Caller uses run_online()/run_offline() without knowing implementation

Usage:
    ```python
    # Implement server
    class MyServer(Server):
        def run_online(self, addr: str, port: int):
            # Start HTTP server
            pass

        def run_offline(self, duration: float):
            # Run batch collection
            pass

    # Factory creates appropriate server
    factory = ServerFactory.get_instance()
    server = factory.create_server()  # Returns best available
    server.run_online()
    ```

Notes:
    Abstract servers (with __abstractmethods__) don't register.
    Import failures in server modules prevent registration gracefully.
"""

from abc import ABC, ABCMeta, abstractmethod
from typing import Optional

from witty_profiler.common.logging import get_logger
from witty_profiler.common.singleton import ThreadSafeSingleton

LOGGER = get_logger(__name__)


class ServerMeta(ABCMeta):
    """Metaclass for automatic server type registration.

    Registers concrete Server subclasses in _registry for factory creation.
    Abstract servers (base classes) skip registration.
    """

    _registry: dict[str, type] = {}

    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)

        # Skip abstract classes
        if hasattr(cls, "__abstractmethods__") and cls.__abstractmethods__:
            return cls

        # Register concrete servers
        mcs._registry[name] = cls
        LOGGER.debug(f"Registered server type: {name}")
        return cls

    @classmethod
    def get_registry(mcs) -> dict[str, type]:
        """Get all registered server types."""
        return mcs._registry


class Server(metaclass=ServerMeta):
    """Abstract base class for Witty Profiler server implementations.

    Defines the interface all server backends must implement.
    Subclasses auto-register via ServerMeta for factory creation.

    Attributes:
        core: WittyProfilerCore instance for collection orchestration

    Abstract Methods:
        run_online: Start HTTP server (blocking)
        run_offline: Run batch collection without server
    """

    def __init__(self, core):
        """Initialize server with WittyProfilerCore instance.

        Args:
            core: WittyProfilerCore singleton for topology collection
        """
        self._core = core

    @abstractmethod
    def run_online(self, addr: str, port: int):
        """Start HTTP server and begin topology collection.

        Should block until shutdown (Ctrl+C or SIGTERM).

        Args:
            addr: Server bind address
            port: Server bind port
        """
        raise NotImplementedError

    @abstractmethod
    def run_offline(self, duration: float):
        """Run collection for fixed duration without HTTP server.

        For batch processing or testing scenarios.

        Args:
            duration: Collection duration in seconds
        """
        raise NotImplementedError


class ServerFactory(ThreadSafeSingleton):
    """Factory for creating server instances based on availability.

    Selects best available server implementation from registry.
    Prefers feature-rich servers (FastAPI) over fallbacks.

    Singleton ensures consistent server selection across application.
    """

    def _ensure_servers_imported(self):
        """Lazy import of server implementations to trigger registration."""
        # Import servers to trigger metaclass registration
        # Import order: fallback first, then feature-rich
        try:
            # pylint: disable=import-outside-toplevel,unused-import
            import witty_profiler.backend.default_server  # noqa: F401
        except ImportError:
            LOGGER.debug("Failed to import default_server")

        try:
            # pylint: disable=import-outside-toplevel,unused-import
            import witty_profiler.backend.fastapi_server  # noqa: F401
        except ImportError:
            LOGGER.debug("Failed to import fastapi_server (dependencies missing)")

    def create_server(
        self, server_type: Optional[str] = None, core=None
    ) -> Optional[Server]:
        """Create server instance of specified or best available type.

        Args:
            server_type: Specific server class name (optional)
            core: WittyProfilerCore instance (creates new if None)

        Returns:
            Server instance or None if no servers available

        Priority:
            1. Specified server_type if provided
            2. FastAPIServer if available
            3. First registered server as fallback
        """
        from witty_profiler.controller.witty_profiler_core import WittyProfilerCore

        # Ensure server modules are imported and registered
        self._ensure_servers_imported()

        if core is None:
            core = WittyProfilerCore.get_instance()

        registry = ServerMeta.get_registry()

        if not registry:
            LOGGER.error("No server implementations registered")
            return None

        # Use specified type if provided
        if server_type:
            if server_type not in registry:
                LOGGER.error(
                    f"Server type '{server_type}' not found. Available: {list(registry.keys())}"
                )
                return None
            return registry[server_type](core)

        # Prefer FastAPI if available
        if "FastAPIServer" in registry:
            LOGGER.info("Using FastAPIServer")
            return registry["FastAPIServer"](core)

        # Fallback to any available server
        fallback_name = next(iter(registry))
        LOGGER.warning(f"FastAPI not available, using fallback: {fallback_name}")
        return registry[fallback_name](core)

    def list_available_servers(self) -> list[str]:
        """List all registered server types.

        Returns:
            List of server class names
        """
        return list(ServerMeta.get_registry().keys())
