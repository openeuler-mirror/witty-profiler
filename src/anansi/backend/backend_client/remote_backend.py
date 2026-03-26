"""Abstract client interface for remote Anansi backend access.

Defines RemoteBackendClient ABC and related error types for communicating
with remote Anansi servers. Concrete implementations (e.g., RestfulRemoteBackendClient)
provide actual HTTP/RPC transport.

Key Components:
    - RemoteBackendClient: Abstract base class defining client interface
    - RemoteBackendClientError: Exception for remote communication failures

Client Operations:
    - start_collection(): Start remote topology collection
    - stop_collection(): Stop remote collection
    - clear_collection(): Clear remote collection state
    - trigger_collection(): Trigger one collection cycle
    - fetch_graph(): Retrieve latest topology graph

Configuration:
    Clients initialized with ServerAddr (host:port) and timeout.
    base_url property constructs full HTTP base URL.

Usage:
    ```python
    # Use concrete implementation
    client = RestfulRemoteBackendClient(
        server_addr=ServerAddr(host=\"192.168.1.100\", port=18090),
        timeout=5.0
    )
    client.start_collection()
    graph_data = client.fetch_graph()
    client.stop_collection()
    ```

Error Handling:
    All methods may raise RemoteBackendClientError on communication failures
    (network errors, timeouts, HTTP errors, invalid responses).

Notes:
    Abstract design allows for different transport implementations
    (HTTP, gRPC, etc.) without changing RemoteCollector code.
"""

from abc import ABC, abstractmethod

from anansi.common.logging import get_logger
from anansi.config_manager.configs import ServerAddr

LOGGER = get_logger(__name__)


class RemoteBackendClientError(RuntimeError):
    """Raised when remote backend HTTP call fails."""


class RemoteBackendClient(ABC):
    """Abstract client for accessing remote Anansi backend."""

    def __init__(self, server_addr: ServerAddr, timeout: float = 5.0):
        self._server_addr = server_addr
        self._timeout = timeout

    @property
    def base_url(self) -> str:
        return f"http://{self._server_addr.host}:{self._server_addr.port}"

    @abstractmethod
    def start_collection(self):
        """Start collection on remote backend."""
        raise NotImplementedError

    @abstractmethod
    def stop_collection(self):
        """Stop collection on remote backend."""

    @abstractmethod
    def clear_collection(self):
        """Clear collection state on remote backend."""
        raise NotImplementedError

    @abstractmethod
    def trigger_collection(self):
        """Trigger one collection cycle on remote backend."""
        raise NotImplementedError

    @abstractmethod
    def fetch_graph(self) -> dict:
        """Fetch the latest graph payload (env/content envelope)."""
        raise NotImplementedError
