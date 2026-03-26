"""Collects inter-process communication topology from IPC mechanism sniffers.

Provides the IPCCollector class for building topology graphs from various
IPC mechanisms including pipes, message queues, semaphores, and Unix sockets.

Supported IPC Types:
    - Unix Domain Socket: AF_UNIX stream and dgram sockets
    - Pipe/FIFO: Anonymous pipes and named pipes (FIFOs)
    - System V Message Queue: msgsnd/msgrcv operations
    - POSIX Message Queue: mq_send/mq_receive operations
    - System V Semaphore: semop operations

Edge Types:
    - IPCEdge: Represents communication channel between two processes

Collection Methods:
    - _get_seed_graph(): Extract IPC endpoints from sniffers
    - get_neighbors_with_edges(): Discover connected processes and channels

Data Sources:
    Uses various IPC sniffers which instrument:
    - unix_stream_sendmsg/unix_dgram_sendmsg kernel functions
    - pipe_read/pipe_write kernel functions
    - msgsnd/msgrcv system calls
    - mq_timedsend/mq_timedreceive system calls
    - semop/semtimedop system calls
    Instrumentation via eBPF.

Configuration:
    IPC sniffer configuration available via config manager.
    Supports filtering by IPC type, PID, etc.

Notes:
    IPC topology complements socket-level view by tracking lightweight
    local communication not visible at TCP/UDP level.
"""

from dataclasses import dataclass
from typing import List, Optional, Set, Tuple

from witty_profiler.collector.local_collector.local_collector import LocalCollector
from witty_profiler.common.logging import get_logger
from witty_profiler.config_manager.config_manager import GlobalConfigManager
from witty_profiler.edge.edge import Edge
from witty_profiler.edge.ipc.ipc_edge import IPCEdge
from witty_profiler.entity.entity_base import Entity
from witty_profiler.entity.node_entity.key_entity import ProcessEntity
from witty_profiler.graph.graph import Graph

LOGGER = get_logger(__name__)


@dataclass
class IPCEventBase:
    timestamp: int
    pid: int
    tid: int
    direction: str
    bytes: int
    count: int


class IPCCollector(LocalCollector):
    """Collector for inter-process communication topology.

    Collects IPC events from multiple sniffers and builds a graph
    representing communication between processes.
    """

    def __init__(
        self,
        pid_filter: Optional[int] = None,
        interval: Optional[int] = None,
    ):
        """Initialize the IPC collector.

        Args:
            pid_filter: Optional PID to filter monitoring
            interval: Sampling interval in seconds (default from config)
        """
        self._config_mngr = GlobalConfigManager.get_instance()
        self._ipc_config = self._config_mngr.get_config().sniffer_config.ipc_sniffer

        self.pid_filter = pid_filter
        self.interval = interval or int(
            self._ipc_config.monitor_report_maximum_interval_by_second
        )

        self._sniffers = {}
        self._started = False
        self._events_cache: List[IPCEventBase] = []
        self._pid_to_entity: dict[int, ProcessEntity] = {}

    @property
    def enable_uds(self) -> bool:
        return self._ipc_config.enable.uds_enable

    @property
    def enable_pipe(self) -> bool:
        return self._ipc_config.enable.pipe_enable

    @property
    def enable_sysv_msg(self) -> bool:
        return self._ipc_config.enable.sysv_msg_enable

    @property
    def enable_posix_mq(self) -> bool:
        return self._ipc_config.enable.posix_mq_enable

    @property
    def enable_sysv_sem(self) -> bool:
        return self._ipc_config.enable.sysv_sem_enable

    def start(self):
        """Start all enabled IPC sniffers."""
        if self._started:
            return

        if self.enable_uds:
            try:
                from witty_profiler.edge.ipc.uds_sniffer import UDSSniffer

                binary_path = self._ipc_config.uds_sniffer_binary_path
                self._sniffers["uds"] = UDSSniffer(binary_path=binary_path)
                self._sniffers["uds"].start(
                    pid_filter=self.pid_filter, interval=self.interval, direction="all"
                )
                LOGGER.info("Started uds sniffer")
            except Exception as e:
                LOGGER.warning(f"Failed to start uds sniffer: {e}")

        if self.enable_pipe:
            try:
                from witty_profiler.edge.ipc.pipe_sniffer import PipeSniffer

                binary_path = self._ipc_config.pipe_sniffer_binary_path
                self._sniffers["pipe"] = PipeSniffer(binary_path=binary_path)
                self._sniffers["pipe"].start(
                    pid_filter=self.pid_filter, interval=self.interval, direction="all"
                )
                LOGGER.info("Started pipe sniffer")
            except Exception as e:
                LOGGER.warning(f"Failed to start pipe sniffer: {e}")

        if self.enable_sysv_msg:
            try:
                from witty_profiler.edge.ipc.sysv_msg_sniffer import SysVMsgSniffer

                binary_path = self._ipc_config.sysv_msg_sniffer_binary_path
                self._sniffers["sysv_msg"] = SysVMsgSniffer(binary_path=binary_path)
                self._sniffers["sysv_msg"].start(
                    pid_filter=self.pid_filter, interval=self.interval, direction="all"
                )
                LOGGER.info("Started sysv_msg sniffer")
            except Exception as e:
                LOGGER.warning(f"Failed to start sysv_msg sniffer: {e}")

        if self.enable_posix_mq:
            try:
                from witty_profiler.edge.ipc.posix_mq_sniffer import POSIXMQSniffer

                binary_path = self._ipc_config.posix_mq_sniffer_binary_path
                self._sniffers["posix_mq"] = POSIXMQSniffer(binary_path=binary_path)
                self._sniffers["posix_mq"].start(
                    pid_filter=self.pid_filter, interval=self.interval, direction="all"
                )
                LOGGER.info("Started posix_mq sniffer")
            except Exception as e:
                LOGGER.warning(f"Failed to start posix_mq sniffer: {e}")

        if self.enable_sysv_sem:
            try:
                from witty_profiler.edge.ipc.sysv_sem_sniffer import SysVSemSniffer

                binary_path = self._ipc_config.sysv_sem_sniffer_binary_path
                self._sniffers["sysv_sem"] = SysVSemSniffer(binary_path=binary_path)
                self._sniffers["sysv_sem"].start(
                    pid_filter=self.pid_filter, interval=self.interval
                )
                LOGGER.info("Started sysv_sem sniffer")
            except Exception as e:
                LOGGER.warning(f"Failed to start sysv_sem sniffer: {e}")

        self._started = True

    def stop(self):
        """Stop all IPC sniffers."""
        for name, sniffer in self._sniffers.items():
            try:
                sniffer.stop()
                LOGGER.info(f"Stopped {name} sniffer")
            except Exception as e:
                LOGGER.warning(f"Failed to stop {name} sniffer: {e}")

        self._sniffers.clear()
        self._started = False

    def clear(self):
        """Clear internal state."""
        self._events_cache.clear()
        self._pid_to_entity.clear()

    def _get_or_create_process_entity(self, pid: int) -> ProcessEntity:
        """Get or create a ProcessEntity for the given PID."""
        if pid not in self._pid_to_entity:
            self._pid_to_entity[pid] = ProcessEntity(pid=pid)
        return self._pid_to_entity[pid]

    def _collect_events(self) -> List[IPCEventBase]:
        """Collect events from all sniffers."""
        events = []

        if "uds" in self._sniffers:
            try:
                uds_events = self._sniffers["uds"].get_events()
                for event in uds_events:
                    events.append(
                        IPCEventBase(
                            timestamp=event.timestamp,
                            pid=event.pid,
                            tid=event.tid,
                            direction=event.direction,
                            bytes=event.bytes,
                            count=event.count,
                        )
                    )
            except Exception as e:
                LOGGER.warning(f"Failed to get uds events: {e}")

        if "pipe" in self._sniffers:
            try:
                pipe_events = self._sniffers["pipe"].get_events()
                for event in pipe_events:
                    events.append(
                        IPCEventBase(
                            timestamp=event.timestamp,
                            pid=event.pid,
                            tid=event.tid,
                            direction=event.direction,
                            bytes=event.bytes,
                            count=event.count,
                        )
                    )
            except Exception as e:
                LOGGER.warning(f"Failed to get pipe events: {e}")

        if "sysv_msg" in self._sniffers:
            try:
                msg_events = self._sniffers["sysv_msg"].get_events()
                for event in msg_events:
                    events.append(
                        IPCEventBase(
                            timestamp=event.timestamp,
                            pid=event.pid,
                            tid=event.tid,
                            direction=event.direction,
                            bytes=event.bytes,
                            count=event.count,
                        )
                    )
            except Exception as e:
                LOGGER.warning(f"Failed to get sysv_msg events: {e}")

        if "posix_mq" in self._sniffers:
            try:
                mq_events = self._sniffers["posix_mq"].get_events()
                for event in mq_events:
                    events.append(
                        IPCEventBase(
                            timestamp=event.timestamp,
                            pid=event.pid,
                            tid=event.tid,
                            direction=event.direction,
                            bytes=event.bytes,
                            count=event.count,
                        )
                    )
            except Exception as e:
                LOGGER.warning(f"Failed to get posix_mq events: {e}")

        return events

    def _get_seed_graph(self) -> Graph:
        """Get the initial graph from collected IPC events."""
        events = self._collect_events()

        nodes: List[Entity] = []
        edges: List[Edge] = []
        seen_pids: Set[int] = set()

        for event in events:
            if event.pid not in seen_pids:
                entity = self._get_or_create_process_entity(event.pid)
                nodes.append(entity)
                seen_pids.add(event.pid)

        return Graph(nodes=nodes, edges=edges)

    def get_neighbors_with_edges(
        self, entity: Entity
    ) -> Tuple[List[Entity], List[Edge]]:
        """Get neighbors and edges for a given entity.

        For IPC, neighbors are processes that communicate with the given process.
        """
        if not isinstance(entity, ProcessEntity):
            return [], []

        neighbors: List[Entity] = []
        edges: List[Edge] = []

        events = self._collect_events()

        for event in events:
            if event.pid != entity.pid:
                continue

            neighbor_entity = self._get_or_create_process_entity(event.pid)

            edge = IPCEdge(
                source_node=entity,
                target_node=neighbor_entity,
            )
            edges.append(edge)

        return neighbors, edges
