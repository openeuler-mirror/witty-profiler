"""Collects network topology from socket sniffers.

Builds a topology graph of inter-process communication via sockets by
instrumenting socket system calls. Creates three edge types to model
socket-level dependencies: HasEdge, BelongEdge, and SocketEdge.

Edge Types Created:
    - HasEdge: Process LISTENS at a local socket (structural relationship)
    - BelongEdge: Socket BELONGS TO a process (inverse of HasEdge)
    - SocketEdge: Process SENDS TO remote socket (data flow)

Seed Graph:
    Starts from all processes discovered by the socket sniffer, then
    expands to find all listening sockets and data flow connections.

Collection Methods:
    - _get_seed_graph(): Extract all processes from sniffer
    - get_neighbors_with_edges(): For a process, find:
        * All sockets it listens on (HasEdge)
        * All sockets listening on remote addresses (SocketEdge)

Data Sources:
    Uses SocketSniffer (see socket_sniffer.py) which instrumentskernel
    socket calls via eBPF or other kernel-level tracing mechanisms.
    Accumulates DataFlowStats (packets, bytes, duration) per socket flow.

Configuration:
    Socket sniffer configuration is managed via Sniffer config module.
    Supports filtering by port range, protocol, etc.

Notes:
    Requires socket sniffer to be running and producing valid records.
    Handles OSError during expansion if sniffer data becomes unavailable.
"""

from __future__ import annotations

from typing import Tuple

from witty_profiler.collector.local_collector.local_collector import LocalCollector
from witty_profiler.common.logging import get_logger
from witty_profiler.config_manager.config_manager import GlobalConfigManager
from witty_profiler.edge.edge import Edge
from witty_profiler.edge.socket.socket_edge import DataFlowStats, SendToSocketEdge
from witty_profiler.edge.socket.socket_sniffer import (
    SocketConnectionInfo,
    SocketSniffer,
    get_socket_sniffer,
)
from witty_profiler.edge.structual.belong import BelongEdge, OwnEdge
from witty_profiler.entity.entity_base import Entity
from witty_profiler.entity.node_entity import ProcessEntity, SocketEntity, ThreadEntity
from witty_profiler.graph.graph import Graph

LOGGER = get_logger(__name__)


class SocketCollector(LocalCollector):
    """
    Collects socket topology graph from socket sniffer
    """

    def start(self):
        """启动SocketSniffer收集数据"""
        LOGGER.debug("Starting SocketSniffer in SocketCollector")
        if not self.sniffer.start():
            raise RuntimeError("Failed to start SocketSniffer")

    def stop(self):
        """停止SocketSniffer收集数据"""
        LOGGER.debug("Stopping SocketSniffer in SocketCollector")
        self.sniffer.stop()

    def clear(self):
        """强制刷新数据"""
        self.sniffer.update_dataframe(drop_previous=True)  # 第一次删除之前数据
        self.sniffer.update_dataframe(drop_previous=True)  # 第二次删除缓冲期数据

    @property
    def record_cnt_total(self) -> int:
        """返回SocketSniffer累计收集的记录数"""
        return self.sniffer.record_cnt_total

    def __init__(self):
        self.sniffer: SocketSniffer = get_socket_sniffer()
        mngr: GlobalConfigManager = GlobalConfigManager.get_instance()
        self._config = mngr.get_config().collector_config.socket_collector_config

    def _get_seed_graph(self) -> Graph:
        seed_nodes: list[Entity] = [
            ProcessEntity.create_ensure_unique_id(pid=pid)
            for pid in self.sniffer.query_all_pids()
        ]
        seed_graph = Graph(nodes=seed_nodes, edges=[])
        return seed_graph

    def get_neighbors_with_edges(
        self, entity: ProcessEntity | SocketEntity
    ) -> Tuple[list[Entity], list[Edge]]:
        """Resolve neighbors of ``entity`` and the edges linking to them."""

        if isinstance(entity, ProcessEntity):
            return self._neighbors_for_process(entity)
        if isinstance(entity, SocketEntity):
            return self._neighbors_for_socket(entity)
        return ([], [])

    def _neighbors_for_process(
        self, process: ProcessEntity
    ) -> Tuple[list[Entity], list[Edge]]:
        """
        Build neighbors for a process node.

        - Local receiving sockets form ``HasEdge``/``BelongEdge``.
        - Outgoing traffic forms ``SocketEdge`` to remote sockets.
        - Owner relationships for remote sockets are inferred if possible.
        """

        neighbors: list[Entity] = []
        edges: list[Edge] = []

        # 找到发往的socket
        conns_send2pid = self.sniffer.query_send_at_pid(process.pid)
        for conn in conns_send2pid:
            if not self._valid_connection(conn):
                continue
            target_socket: SocketEntity = SocketEntity.create_ensure_unique_id(
                socket_addr=conn.remote_addr,
                socket_port=conn.remote_port,
                socket_type=conn.connection_type,
            )
            neighbors.append(target_socket)

            create_thread_node: bool = (
                conn.local_tid is not None
                and self._config.enable_thread_node
                and self._valid_connection(conn)
            )

            # 不创建线程节点时，进程直接连接到套接字
            # Process --SocketEdge--> Socket
            if not create_thread_node:
                edges.append(
                    SendToSocketEdge(
                        source_node=process,
                        target_node=target_socket,
                        connection_type=conn.connection_type,
                        data_flow=DataFlowStats(
                            start_time=conn.start_time,
                            end_time=conn.end_time,
                            data_size=conn.data_size_total,
                            packets_cnt=conn.packet_cnt,
                        ),
                    )
                )
            else:
                # 创建线程节点时，按照线程节点连接
                # Process --OwnEdge--> Thread --SocketEdge--> Socket
                src_process = ProcessEntity.create_ensure_unique_id(
                    pid=conn.local_pid,
                )
                thread_entity = ThreadEntity.create_ensure_unique_id(
                    tid=conn.local_tid,
                    process=src_process,
                )

                neighbors.append(src_process)
                neighbors.append(thread_entity)
                edges.extend(
                    [
                        OwnEdge.create_ensure_unique_id(
                            source_node=src_process,
                            target_node=thread_entity,
                        ),
                        SendToSocketEdge(
                            source_node=thread_entity,
                            target_node=target_socket,
                            connection_type=conn.connection_type,
                            data_flow=DataFlowStats(
                                start_time=conn.start_time,
                                end_time=conn.end_time,
                                data_size=conn.data_size_total,
                                packets_cnt=conn.packet_cnt,
                            ),
                        ),
                    ]
                )

        # 本地监听Socket
        conns_recvatpid = self.sniffer.query_recv_at_pid(process.pid)
        for conn in conns_recvatpid:
            if not self._valid_connection(conn):
                continue
            local_socket = SocketEntity.create_ensure_unique_id(
                socket_addr=conn.local_addr,
                socket_port=conn.local_port,
                socket_type=conn.connection_type,
            )

            neighbors.append(local_socket)

            create_thread_node: bool = (
                conn.local_tid is not None
                and self._config.enable_thread_node
                and self._valid_connection(conn)
            )

            if not create_thread_node:
                # 进程节点与套接字节点的连接关系
                # Process --OwnEdge--> Socket
                edges.append(
                    OwnEdge.create_ensure_unique_id(
                        source_node=process, target_node=local_socket
                    )
                )
                edges.append(
                    BelongEdge.create_ensure_unique_id(
                        source_node=local_socket, target_node=process
                    )
                )
            else:
                # 创建线程节点时，按照线程节点连接
                # Process --OwnEdge--> Thread --OwnEdge--> Socket
                # Socket --BelongEdge--> Thread
                src_process = process
                thread_entity = ThreadEntity.create_ensure_unique_id(
                    tid=conn.local_tid,
                    process=src_process,
                )

                neighbors.append(src_process)
                neighbors.append(thread_entity)
                edges.extend(
                    [
                        OwnEdge.create_ensure_unique_id(
                            source_node=src_process,
                            target_node=thread_entity,
                        ),
                        OwnEdge.create_ensure_unique_id(
                            source_node=thread_entity,
                            target_node=local_socket,
                        ),
                        BelongEdge.create_ensure_unique_id(
                            source_node=local_socket,
                            target_node=thread_entity,
                        ),
                    ]
                )

        return neighbors, edges

    def _neighbors_for_socket(
        self, socket: SocketEntity
    ) -> Tuple[list[Entity], list[Edge]]:
        """
        Build neighbors for a socket node.

        - The owning process (if known or discoverable) links via
          ``HasEdge``/``BelongEdge``.
        - Sender processes targeting this socket link via ``SocketEdge``.
        """

        neighbors: list[Entity] = []
        edges: list[Edge] = []

        # 找本端口所属的进程
        # 1) Owning process/thread (listening at this socket)
        for conn in self.sniffer.query_recv_at_socket(
            socket.socket_addr, socket.socket_port
        ):
            if not self._valid_connection(conn):

                continue
            listener_process = ProcessEntity.create_ensure_unique_id(pid=conn.local_pid)
            create_thread_node: bool = (
                conn.local_tid is not None
                and self._config.enable_thread_node
                and self._valid_connection(conn)
            )
            neighbors.append(listener_process)
            # 不创建线程节点时，进程直接连接到套接字
            # Process --OwnEdge--> Socket
            if not create_thread_node:
                edges.extend(
                    [
                        OwnEdge.create_ensure_unique_id(
                            source_node=listener_process,
                            target_node=socket,
                        ),
                        BelongEdge.create_ensure_unique_id(
                            source_node=socket,
                            target_node=listener_process,
                        ),
                    ]
                )
                continue
            # 创建线程节点时，按照线程节点连接
            # Process --OwnEdge--> Thread --OwnEdge--> Socket
            listener_thread = ThreadEntity.create_ensure_unique_id(
                tid=conn.local_tid,
                process=listener_process,
            )
            neighbors.append(listener_thread)
            edges.extend(
                [
                    OwnEdge(
                        source_node=listener_process,
                        target_node=listener_thread,
                    ),
                    OwnEdge(
                        source_node=listener_thread,
                        target_node=socket,
                    ),
                ]
            )

        # 2) Processes sending data to this socket
        for conn in self.sniffer.query_send_to_socket(
            socket.socket_addr, socket.socket_port
        ):
            if not self._valid_connection(conn):
                continue
            sender_process = ProcessEntity.create_ensure_unique_id(pid=conn.local_pid)
            neighbors.append(sender_process)

            create_thread_node: bool = (
                conn.local_tid is not None
                and self._config.enable_thread_node
                and self._valid_connection(conn)
            )
            # 不创建线程节点时，进程直接连接到套接字
            # Process --SocketEdge--> Socket
            if not create_thread_node:
                edges.append(
                    SendToSocketEdge(
                        source_node=sender_process,
                        target_node=socket,
                        connection_type=conn.connection_type,
                        data_flow=DataFlowStats(
                            start_time=conn.start_time,
                            end_time=conn.end_time,
                            data_size=conn.data_size_total,
                            packets_cnt=conn.packet_cnt,
                        ),
                    )
                )
                continue
            # 创建线程节点时，按照线程节点连接
            # Process --OwnEdge--> Thread --SocketEdge--> Socket
            sender_thread = ThreadEntity.create_ensure_unique_id(
                tid=conn.local_tid,
                process=sender_process,
            )
            neighbors.append(sender_thread)
            edges.extend(
                [
                    OwnEdge.create_ensure_unique_id(
                        source_node=sender_process,
                        target_node=sender_thread,
                    ),
                    SendToSocketEdge(
                        source_node=sender_thread,
                        target_node=socket,
                        connection_type=conn.connection_type,
                        data_flow=DataFlowStats(
                            start_time=conn.start_time,
                            end_time=conn.end_time,
                            data_size=conn.data_size_total,
                            packets_cnt=conn.packet_cnt,
                        ),
                    ),
                ]
            )

        return neighbors, edges

    def _valid_connection(self, conn: SocketConnectionInfo) -> bool:
        """Check if a connection passes the filtering criteria."""
        if not self._config.enable_filter:
            return True
        if conn.packet_cnt < self._config.filter_conn_packet_cnt:
            return False
        if conn.data_size_total < self._config.filter_conn_data_size:
            return False
        return True

    def supported_source_node_type(self) -> set[type]:
        return {ProcessEntity, SocketEntity}


__all__ = ["SocketCollector"]
