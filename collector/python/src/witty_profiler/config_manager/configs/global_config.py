import os
from dataclasses import dataclass, field
from typing import Optional

from witty_profiler.common.constants import WittyProfilerServerConstants as ASC
from witty_profiler.common.constants import SocketSnifferConstants
from witty_profiler.config_manager.configs.server_config import ServerConfig
from witty_profiler.entity.entity_base import Entity

from .collector_config import CollectorConfig
from .server_config import RemoteSlaveConfig, ServerAddr
from .sniffer_config import SnifferConfig


@dataclass
class GlobalConfig:
    tmp_dir: str = field(default_factory=lambda: "local/witty_profiler/run/")
    sniffer_config: SnifferConfig = field(default_factory=lambda: SnifferConfig())
    collector_config: CollectorConfig = field(default_factory=lambda: CollectorConfig())
    server_config: ServerConfig = field(default_factory=lambda: ServerConfig())

    def __post_init__(self):
        if isinstance(self.sniffer_config, dict):
            self.sniffer_config = SnifferConfig(**self.sniffer_config)
        if isinstance(self.collector_config, dict):
            self.collector_config = CollectorConfig(**self.collector_config)
        if isinstance(self.server_config, dict):
            self.server_config = ServerConfig(**self.server_config)
        os.makedirs(self.tmp_dir, exist_ok=True)
