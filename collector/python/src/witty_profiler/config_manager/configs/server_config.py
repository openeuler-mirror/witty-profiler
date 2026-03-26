import os
from dataclasses import dataclass, field
from typing import Optional

from witty_profiler.common.constants import WittyProfilerServerConstants as ASC
from witty_profiler.common.constants import SocketSnifferConstants
from witty_profiler.entity.entity_base import Entity


@dataclass
class ServerAddr:
    host: str = field(default_factory=lambda: ASC.DEFAULT_HOST)
    port: int = field(default_factory=lambda: ASC.DEFAULT_PORT)


@dataclass
class ServerConfig:
    """HTTP server configuration.

    Attributes:
        host: Server bind address (default: 0.0.0.0)
        port: Server bind port (default: 18090)
        preferred_backend: Preferred server implementation name
            (e.g., "FastAPIServer", "OnlineDisabledServer", None for auto-select)

    Notes:
        Defaults filled from WittyProfilerServerConstants.
        preferred_backend=None triggers automatic best-available selection.
    """

    server_addr: ServerAddr = field(
        default_factory=lambda: ServerAddr(ASC.DEFAULT_HOST, ASC.DEFAULT_PORT)
    )
    preferred_backend: Optional[str] = None  # None = auto-select

    def __post_init__(self):
        if isinstance(self.server_addr, dict):
            self.server_addr = ServerAddr(**self.server_addr)
        if not isinstance(self.server_addr, ServerAddr):
            raise ValueError("server_addr must be a ServerAddr instance or a dict")


@dataclass
class RemoteSlaveConfig:
    """
    Configuration for slave servers
    """

    slave_addr: Optional[ServerAddr] = field(default=None)
    query_interval_by_second: float = field(default=10.0)

    def __str__(self):
        return f"[addr:{self.slave_addr}]query per {self.query_interval_by_second}s"

    def __post_init__(self):
        # 注意禁止自己访问自己造成循环
        if isinstance(self.slave_addr, dict):
            self.slave_addr = ServerAddr(**self.slave_addr)
