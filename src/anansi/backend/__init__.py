"""Backend server implementations for Anansi HTTP API.

Provides pluggable server backends with automatic registration via metaclass.
Supports multiple implementations (FastAPI, fallback) with factory-based creation.

Available Servers:
    - FastAPIServer: Full-featured REST API (requires fastapi/uvicorn)
    - OnlineDisabledServer: Fallback when dependencies unavailable

Factory Usage:
    ```python
    from anansi.backend import ServerFactory

    # Create server (auto-detects available implementation)
    server = ServerFactory.get_instance().create_server()

    # Or specify type explicitly
    server = ServerFactory.get_instance().create_server("FastAPIServer")
    ```

Notes:
    Servers register automatically via ServerMeta metaclass when imported.
    Import failures (e.g., missing fastapi) skip registration gracefully.
    Server modules are imported lazily to avoid circular dependencies.
"""

# Export base classes for external use
from .base import Server, ServerFactory

__all__ = ["Server", "ServerFactory"]
