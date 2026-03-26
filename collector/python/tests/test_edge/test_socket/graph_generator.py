import contextlib
import math
import random
import socket
from dataclasses import dataclass

import numpy as np

from witty_profiler.common.constants import CONNECTION_TYPE_TCP, CONNECTION_TYPE_UDP
from witty_profiler.edge.edge import Edge
from witty_profiler.edge.socket.socket_edge import DataFlowStats, SendToSocketEdge
from witty_profiler.edge.structual.belong import BelongEdge, OwnEdge
from witty_profiler.entity.node_entity import ProcessEntity, SocketEntity
from witty_profiler.graph.graph import Graph


@dataclass
class SocketGraphGenerationConfig:
    process_num: int = 4
    ADDR: str = "127.0.0.1"  # socket绑定地址
    listener_process_ratio: float = 1.0  # 输入进程中有多少进程有监听socket的比率
    listener_minimum_sender_count: int = 1  # 发往每个监听socket最少有多少个发送进程
    sender_minimum_receiver_count: int = 1  # 每个进程最少连接多少个监听socket
    connection_probability: float = 0.2  # 进程连接监听socket的概率

    allow_self_connection: bool = False  # 是否允许进程发往自身建立的Socket连接

    allowed_connection_types: list[str] = (
        CONNECTION_TYPE_TCP,
        CONNECTION_TYPE_UDP,
    )  # 连接类型


class SocketGraphGenerator:
    """
    基于socket的流量图生成器
    通过配置的参数，基于输入的进程实体列表，生成连接图
    """

    def __init__(self, config: SocketGraphGenerationConfig):
        self.config = config

    def generate(self) -> Graph:
        """
        根据配置生成一个graph
        """

        process_entities = [ProcessEntity() for i in range(self.config.process_num)]
        listener_cnt = int(self.config.process_num * self.config.listener_process_ratio)

        nodes = process_entities.copy()
        edges: list[Edge] = []

        listener_processes = random.sample(process_entities, listener_cnt)
        protocols = [
            random.choice(self.config.allowed_connection_types)
            for _ in range(listener_cnt)
        ]
        listen_ports = self._allocate_free_port_fixed(protocols)
        for i, (listen_process, protocol, port) in enumerate(
            zip(listener_processes, protocols, listen_ports)
        ):
            listen_socket = SocketEntity(
                socket_type=protocol,
                socket_addr=self.config.ADDR,
                socket_port=port,
            )
            nodes.append(listen_socket)
            edges.append(
                OwnEdge(
                    source_node=listen_process,
                    target_node=listen_socket,
                )
            )
            edges.append(
                BelongEdge(
                    source_node=listen_socket,
                    target_node=listen_process,
                )
            )

            # 接下来找sender
            sender_processes = self._select_sender_processes(
                candidates=[
                    e
                    for e in process_entities
                    if self.config.allow_self_connection or e is not listen_process
                ],
                probability=self.config.connection_probability,
            )
            for sender_process in sender_processes:
                edge = SendToSocketEdge(
                    connection_type=protocol,
                    source_node=sender_process,
                    target_node=listen_socket,
                )
                edges.append(edge)
        return Graph(nodes=sorted(nodes), edges=sorted(edges))

    def _allocate_free_port_fixed(self, protocols: list[str]) -> list[int]:
        # 固定端口
        n = len(protocols)
        return list(range(20000, 20000 + n))

    def _allocate_free_port_dynamic(self, protocols: list[str]) -> list[int]:
        """通过绑定端口0的方式为指定协议挑选空闲端口"""
        ports = set()
        n = len(protocols)
        for protocol in protocols:
            sock_type = (
                socket.SOCK_DGRAM
                if protocol == CONNECTION_TYPE_UDP
                else socket.SOCK_STREAM
            )
            for _ in range(10):
                port = None
                with contextlib.closing(
                    socket.socket(socket.AF_INET, sock_type)
                ) as sock:
                    sock.bind((self.config.ADDR, 0))
                    port = sock.getsockname()[1]
                if port not in ports:
                    ports.add(port)
                    break
            if len(ports) >= n:
                break
        if len(ports) < n:
            raise RuntimeError("无法分配足够可用端口")
        return ports

    def _select_sender_processes(
        self,
        candidates: list[ProcessEntity],
        probability: float,
    ) -> list[ProcessEntity]:

        if len(candidates) < self.config.listener_minimum_sender_count:
            raise RuntimeError(
                "Cannot select enough sender processes %s < %s"
                % (len(candidates), self.config.listener_minimum_sender_count)
            )

        is_sender_probs = [random.random() for _ in range(len(candidates))]
        sender_list = [
            i
            for i, p in enumerate(is_sender_probs)
            if p < self.config.connection_probability
        ]
        left = [
            i
            for i, p in enumerate(is_sender_probs)
            if p >= self.config.connection_probability
        ]
        if len(sender_list) < self.config.listener_minimum_sender_count:
            # 不够的话，随机补齐
            sender_list += random.choices(
                left, k=self.config.listener_minimum_sender_count - len(sender_list)
            )
        selected_senders = [candidates[i] for i in sender_list]
        return selected_senders


__all__ = ["SocketTrafficGenerator", "SocketTrafficGeneratorConfig"]
