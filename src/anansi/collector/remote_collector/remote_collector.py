"""Remote Anansi Server collector via REST API.

Collects topology graphs from remote Anansi servers through HTTP requests,
enabling distributed topology aggregation across multiple machines.

Key Components:
    - RemoteCollector: Collector that fetches graphs from remote servers
    - RemoteBackendClient: Abstract HTTP client interface (pluggable)
    - RestfulRemoteBackendClient: Default HTTP client using urllib
    - RemoteSlaveConfig: Configuration for remote server address and frequency

Features:
    - Request throttling via query_frequency_by_second (minimum interval: 1/f)
    - Namespace isolation using remote EnvInfo.local_ip (prevents ID collisions)
    - Automatic start/stop of remote server collection via /control endpoints
    - Graph caching with configurable refresh intervals

Collection Flow:
    1. POST /control/start - Start remote collection
    2. GET /graph - Fetch latest topology graph
    3. Namespace remote entities with remote IP: [<remote_ip>]{entity_type}_{id}
    4. POST /control/stop - Stop remote collection on cleanup

Configuration:
    RemoteSlaveConfig must specify slave_addr (host:port of remote server).
    Example: RemoteSlaveConfig(slave_addr="192.168.1.100:18090")

API Protocol:
    Remote server must implement docs/backend/api.md envelope format:
    ```json
    {
        "env": {"local_ip": "...", "hostname": "..."},
        "content": {"nodes": [...], "edges": [...]}
    }
    ```

Notes:
    - Requires remote Anansi server running with FastAPI backend
    - Raises RemoteBackendClientError on HTTP failures
    - Remote entities are automatically namespaced to avoid conflicts
    - Thread-safe via internal lock for start/stop operations
"""

import threading
import time
from typing import Optional, Tuple

from anansi.backend.backend_client import (
    RemoteBackendClient,
    RemoteBackendClientError,
    RestfulRemoteBackendClient,
)
from anansi.collector.collector_base import Collector
from anansi.common.constants import AnansiServerConstants as ASC
from anansi.common.env_manager import EnvInfo
from anansi.common.logging import get_logger
from anansi.config_manager.configs import RemoteSlaveConfig
from anansi.edge.edge import Edge
from anansi.entity.entity_base import Entity
from anansi.entity.entity_namespace import EntityNameSpace
from anansi.graph.graph import Graph

LOGGER = get_logger(__name__)


class RemoteCollector(Collector):
    def __init__(
        self,
        slave_config: RemoteSlaveConfig,
        backend_client: Optional[RemoteBackendClient] = None,
    ):
        super().__init__()
        if slave_config.slave_addr is None:
            raise ValueError("RemoteSlaveConfig.slave_addr is required")

        self._slave_config: RemoteSlaveConfig = slave_config
        self._backend_client: RemoteBackendClient = (
            backend_client or RestfulRemoteBackendClient(slave_config.slave_addr)
        )
        self._cached_graph: Graph = Graph()
        self._last_sync_ts: Optional[float] = None
        if (
            self._slave_config.query_interval_by_second
            < ASC.REMOTE_QUERY_MIN_INTERVAL_BY_SECOND
        ):
            self._slave_config.query_interval_by_second = (
                ASC.REMOTE_QUERY_MIN_INTERVAL_BY_SECOND
            )
        self._started: bool = False
        # Background sync thread control
        self._sync_thread: Optional[threading.Thread] = None
        self._stop_event: threading.Event = threading.Event()
        self._graph_lock: threading.RLock = threading.RLock()

    def is_valid(self) -> bool:
        try:
            _cached_graph = self._backend_client.fetch_graph()
            return isinstance(_cached_graph, dict)
        except RemoteBackendClientError:
            return False
        except TimeoutError:
            return False
        return False

    def start(self):
        """Start the remote server collection via REST API and background sync thread."""
        if self._started:
            LOGGER.debug(
                "RemoteCollector already started for %s", self._backend_client.base_url
            )
            return
        self._backend_client.start_collection()
        # Start background thread for periodic graph sync
        self._stop_event: threading.Event = threading.Event()
        self._stop_event.clear()
        self._sync_thread = threading.Thread(
            target=self._sync_loop,
            daemon=True,
            name="RemoteCollector-{}".format(self._backend_client.base_url),
        )
        self._sync_thread.start()
        self._started = True
        LOGGER.info(
            "RemoteCollector started with %.1fs sync interval for %s",
            self._slave_config.query_interval_by_second,
            self._backend_client.base_url,
        )

    def stop(self):
        """Stop the remote server collection and background sync thread."""
        if not self._started:
            LOGGER.debug(
                "RemoteCollector already stopped for %s", self._backend_client.base_url
            )
            return
        # Signal background thread to stop
        self._stop_event.set()
        if self._sync_thread and self._sync_thread.is_alive():
            LOGGER.debug("Waiting for sync thread to stop...")
            self._sync_thread.join(timeout=5.0)
            if self._sync_thread.is_alive():
                LOGGER.warning("Sync thread did not stop within timeout")
        self._backend_client.stop_collection()
        self._started = False
        LOGGER.info("RemoteCollector stopped for %s", self._backend_client.base_url)

    def clear(self):
        """Clear the remote server collection's internal state."""
        self._backend_client.clear_collection()
        self._cached_graph = Graph()
        self._last_sync_ts = None

    def _get_seed_graph(self) -> Graph:
        """Get the whole graph nodes to start collection from."""
        with self._graph_lock:
            return self._cached_graph

    def get_neighbors_with_edges(
        self, entity: Entity
    ) -> Tuple[list[Entity], list[Edge]]:
        """
        Get the neighbors of the given entity with edges.
        As the seed graph has already contained all known entities and edges,
        there is no need to expand any further.
        """
        return [], []

    def trigger_collect(self):
        """
        Actively trigger a remote graph sync, bypassing interval throttling.
        This forces an immediate fetch regardless of when the last sync occurred.
        """
        if not self._started:
            LOGGER.warning("RemoteCollector not started, cannot trigger collection")
            return
        try:
            LOGGER.debug("trigger_collect: forcing immediate sync")
            self._do_sync()
        except RemoteBackendClientError as e:
            LOGGER.error(
                "Forced sync failed for %s: %s", self._backend_client.base_url, e
            )
            raise
        except Exception as e:
            LOGGER.exception("Unexpected error in forced sync: %s", e)
            raise

    def _sync_loop(self):
        """
        Background thread loop that periodically syncs remote graph.
        Runs at query_interval_by_second frequency.
        """
        while not self._stop_event.is_set():
            try:
                self._do_sync()
            except RemoteBackendClientError as e:
                LOGGER.error(
                    "Remote sync failed for %s: %s", self._backend_client.base_url, e
                )
            except Exception as e:
                LOGGER.exception("Unexpected error in sync loop: %s", e)

            # Wait for next interval or stop signal
            self._stop_event.wait(self._slave_config.query_interval_by_second)

    def _do_sync(self):
        """
        Perform actual remote sync with thread safety.
        Fetches graph from remote server and updates cached graph.
        """
        start_time = time.monotonic()
        self._backend_client.trigger_collection()
        payload = self._backend_client.fetch_graph()

        env_dict = payload.get("env", {}) if isinstance(payload, dict) else {}
        graph_dict = payload.get("content", {}) if isinstance(payload, dict) else {}

        new_graph = self._on_recv_graph(env_dict, graph_dict)

        # Thread-safe update of cached graph
        with self._graph_lock:
            self._cached_graph = new_graph

            self._last_sync_ts = time.monotonic()
            elapsed = self._last_sync_ts - start_time
            LOGGER.debug(
                "Remote sync completed in %.3fs, got %d nodes %d edges",
                elapsed,
                len(new_graph.nodes),
                len(new_graph.edges),
            )

    def _on_recv_graph(self, env_dict: dict, graph_dict: dict) -> Graph:
        """Handle received graph payload"""
        env_info = EnvInfo(**env_dict)
        with EntityNameSpace(env_info):
            graph = Graph(**graph_dict)
            return graph

    def clear(self):
        """Clear the remote server collection's internal state."""
        self._backend_client.clear_collection()
        with self._graph_lock:
            self._cached_graph = Graph()
        self._last_sync_ts = None
