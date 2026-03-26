"""Fallback server when FastAPI dependencies unavailable.

Provides minimal functionality for offline mode only. Online mode raises
helpful error directing users to install dependencies.

Usage:
    Automatically selected by ServerFactory when FastAPI not installed.

    ```python
    # Offline mode works without dependencies
    server.run_offline(duration=30)

    # Online mode provides clear error message
    server.run_online()  # -> RuntimeError with install instructions
    ```

Notes:
    Always registers (no import dependencies). Acts as safety net when
    no feature-rich servers available.
"""

import json
import time

from witty_profiler.backend.base import Server
from witty_profiler.common.logging import get_logger
from witty_profiler.config_manager.config_manager import GlobalConfigManager
from witty_profiler.graph.graph import Graph

LOGGER = get_logger(__name__)


class OnlineDisabledServer(Server):
    """Fallback server with offline-only support.

    Provides run_offline() for batch collection but raises error on
    run_online() with instructions to install FastAPI.

    Use Case:
        Testing/batch processing without HTTP server dependencies.
    """

    def run_offline(self, duration: float):
        """Run collection for fixed duration and output final graph.

        Starts collectors, waits, stops, triggers final collection,
        and prints JSON to stdout.

        Args:
            duration: Collection duration in seconds
        """
        self._core.start()
        LOGGER.info(f"Running Witty Profiler offline for {duration} seconds...")
        time.sleep(duration)
        LOGGER.info(f"Stopping Witty Profiler after {duration} seconds...")
        LOGGER.debug("Collection complete. Stopping core...")
        self._core.stop()
        LOGGER.debug("Triggering final collection...")
        self._core.trigger_collect()
        LOGGER.debug("Getting final graph...")
        graph: Graph = self._core.get_last_graph()
        LOGGER.debug("Dumping graph to topology_graph.json")
        LOGGER.info("Final collected graph: %s", graph.describe())

        target_json_path = GlobalConfigManager().convert_to_tmp_path(
            "topology_graph.json"
        )
        target_text_path = GlobalConfigManager().convert_to_tmp_path(
            "topology_graph.txt"
        )

        with open(target_json_path, "w") as f:
            f.write(json.dumps(graph.model_dump(), indent=2))
        with open(target_text_path, "w") as f:
            f.write(graph.describe())

        LOGGER.report("Topology summary written to %s", target_text_path)
        LOGGER.info("Topology json written to %s", target_json_path)

    def run_online(self, addr: str, port: int):
        """Raise error with installation instructions.

        Args:
            addr: Ignored
            port: Ignored

        Raises:
            RuntimeError: With FastAPI installation instructions
        """
        error_msg = (
            "Online mode requires FastAPI and uvicorn.\n"
            "Install with: uv sync --group server\n"
            "Or: pip install fastapi uvicorn\n"
            "\n"
            "Offline mode is available without dependencies:\n"
            "  python -m witty_profiler --offline --duration 30"
        )
        LOGGER.error(error_msg)
        raise RuntimeError(error_msg)
