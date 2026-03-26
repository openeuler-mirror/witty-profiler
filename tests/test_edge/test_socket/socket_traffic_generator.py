"""
Socket Traffic generator

用于：
0. 提供一个入口函数start(...)
    设置signal handler, 捕获终止信号为KeyboardInterrupt（下述类似，此后不再重复）
    根据参数调用如下过程
1. 自动构建一副Socket连接图graph,包含:
    节点：Process节点，Socket节点（Recv）
    边：HasEdge, BelongEdge, SocketEdge(SenderProcss to RecvSocket)
    其中Process节点初始时可能PID未分配，等后续创建进程后分配
2. 根据Socket连接图
    创建子进程（每个子进程对应一个ProcessEntity），获取PID，更新连接图graph：
        将连接图的json写入 **当前文件同目录下的** `local/ground_truth.json` 文件中
        将连接图的describe()写入 **当前文件同目录下的** `local/ground_truth.log` 文件中
    各个子进程根据自身的HasEdge关系，创建监听Socket，监听socket不断接收数据，然后
    各个子进程根据自身的SocketEdge关系，启动线程向目标Socket不断发送数据
        （发送间隔由一个入口函数start_traffic_generator的参数控制）
    主进程沉睡等待直到收到结束/终止信号
3. 当捕获到终止信号时，主进程发送终止信号给各个子进程
    各个子进程捕获到终止信号时，发送结束标志和SIGTERM信号给各个子线程，等待各个子线程退出后，子进程优雅退出
    各个子进程退出后，主进程优雅退出

"""

from __future__ import annotations

import contextlib
import json
import multiprocessing
import os
import random
import signal
import socket
import threading
import time
from dataclasses import dataclass, field
from typing import Iterable, Optional

from anansi.common.constants import CONNECTION_TYPE_TCP, CONNECTION_TYPE_UDP
from anansi.common.logging import get_logger
from anansi.edge.socket.socket_edge import DataFlowStats, SendToSocketEdge
from anansi.edge.structual.belong import BelongEdge, OwnEdge
from anansi.entity.node_entity import ProcessEntity, SocketEntity
from anansi.graph.graph import Graph
from tests.test_edge.test_socket.graph_generator import (
    SocketGraphGenerationConfig,
    SocketGraphGenerator,
)

LOGGER = get_logger(__name__)


@dataclass
class SocketTrafficGeneratorConfig:
    tgt_ground_truth_json_path: str = os.path.join(
        os.path.dirname(__file__), "local", "ground_truth.json"
    )
    tgt_ground_truth_log_path: str = os.path.join(
        os.path.dirname(__file__), "local", "ground_truth.log"
    )
    process_number: int = 3  # 生成流量的进程节点（ProcessEntity）数目
    graph_generator_config: SocketGraphGenerationConfig = field(
        default_factory=lambda: SocketGraphGenerationConfig()
    )
    send_interval: float = 0.1  # 发送间隔(单位秒)
    connection_duration: int = 5e10  # 每次连接持续的发送次数


@dataclass
class _RecvSocketRuntime:
    """接收socket运行期描述"""

    host: str
    port: int
    protocol: str


@dataclass
class _SendTargetRuntime:
    """发送目标运行期描述"""

    host: str
    port: int
    protocol: str


@dataclass
class _ProcessRuntimePlan:
    """进程运行计划，包含自身节点和收发配置"""

    entity: ProcessEntity
    recv_sockets: list[_RecvSocketRuntime]
    send_targets: list[_SendTargetRuntime]


@dataclass
class _WorkerRuntimeConfig:
    """子进程执行所需的序列化配置"""

    label: str
    recv_sockets: list[_RecvSocketRuntime]
    send_targets: list[_SendTargetRuntime]
    send_interval: float
    connection_duration: int


class SocketTrafficGenerator:
    def __init__(self, config: Optional[SocketTrafficGeneratorConfig] = None):
        """初始化流量生成器并准备运行期状态"""

        self.config = config or SocketTrafficGeneratorConfig()
        self._graph: Graph | None = None
        self._runtime_plans: list[_ProcessRuntimePlan] = []
        self._child_processes: list[multiprocessing.Process] = []
        self._stop_event = threading.Event()
        self._signal_handlers: dict[int, object] = {}
        self._running = False

    def _generate_graph(self) -> Graph:
        """
        构建socket连接图
        包含Process节点，Socket节点（Recv）
        边：
            HasEdge    (OwnerProcess to ListenerSocket)
            BelongEdge (ListenerSocket to OwnerProcess)
            SocketEdge (SenderProcss to RecvSocket)
        """
        generator = SocketGraphGenerator(self.config.graph_generator_config)
        graph = generator.generate()
        return graph

    def _build_runtime_plan(self, graph: Graph) -> list[_ProcessRuntimePlan]:
        """基于图结构生成子进程的运行期计划"""

        plans: dict[str, _ProcessRuntimePlan] = {}
        for node in graph.nodes:
            if isinstance(node, ProcessEntity):
                plans[node.global_id] = _ProcessRuntimePlan(
                    entity=node, recv_sockets=[], send_targets=[]
                )

        for edge in graph.edges:
            if isinstance(edge, OwnEdge):
                if not isinstance(edge.source_node, ProcessEntity):
                    continue
                if not isinstance(edge.target_node, SocketEntity):
                    continue

                socket_node: SocketEntity = edge.target_node
                plan = plans.get(edge.source_node.global_id)
                if plan:
                    plan.recv_sockets.append(
                        _RecvSocketRuntime(
                            host=socket_node.socket_addr,
                            port=socket_node.socket_port,
                            protocol=socket_node.socket_type,
                        )
                    )
            elif isinstance(edge, SendToSocketEdge):
                plan = plans.get(edge.source_node.global_id)
                if plan:
                    plan.send_targets.append(
                        _SendTargetRuntime(
                            host=edge.target_node.socket_addr,
                            port=edge.target_node.socket_port,
                            protocol=edge.connection_type,
                        )
                    )

        return list(plans.values())

    def _start_child_processes(self, plans: list[_ProcessRuntimePlan]):
        """根据计划启动子进程并记录PID"""

        self._child_processes = []
        for i, plan in enumerate(plans):
            worker_cfg = _WorkerRuntimeConfig(
                label=f"w{i}",
                recv_sockets=plan.recv_sockets,
                send_targets=plan.send_targets,
                send_interval=self.config.send_interval,
                connection_duration=self.config.connection_duration,
            )
            process = multiprocessing.Process(
                target=SocketTrafficGenerator._worker_entry, args=(worker_cfg,)
            )
            process.start()
            if process.pid:
                # 此时才获得PID，更新Process节点
                plan.entity.pid = process.pid
            self._child_processes.append(process)

    def _persist_ground_truth(self, graph: Graph):
        """将生成的ground truth写入文件供测试使用"""
        LOGGER.debug("Persisting ground truth graph")
        LOGGER.debug("Graph description:\n%s", graph.describe())

        os.makedirs(
            os.path.dirname(self.config.tgt_ground_truth_json_path), exist_ok=True
        )
        with open(self.config.tgt_ground_truth_json_path, "w", encoding="utf-8") as fp:
            json.dump(graph.model_dump(), fp, ensure_ascii=False, indent=2)

        os.makedirs(
            os.path.dirname(self.config.tgt_ground_truth_log_path), exist_ok=True
        )
        with open(self.config.tgt_ground_truth_log_path, "w", encoding="utf-8") as fp:
            fp.write(graph.describe())

    def _setup_signal_handlers(self):
        """注册主进程需要的信号处理器"""

        self._signal_handlers = {}
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                previous = signal.getsignal(sig)
                signal.signal(sig, self._handle_stop_signal)
                self._signal_handlers[sig] = previous
            except ValueError:
                LOGGER.warning("当前线程无法注册信号 %s", sig)

    def _restore_signal_handlers(self):
        """在停止后恢复原始的signal handler"""

        for sig, handler in self._signal_handlers.items():
            try:
                signal.signal(sig, handler)
            except ValueError:
                LOGGER.warning("无法恢复信号 %s 的处理器", sig)
        self._signal_handlers.clear()

    def _handle_stop_signal(self, signum, _frame):
        """捕获终止信号并触发停止流程"""

        LOGGER.info(
            "On recv termination signal %s, raise keyboard interrupt...", signum
        )
        if not self._stop_event.is_set():
            self._stop_event.set()
            raise KeyboardInterrupt

    def start(self):
        """
        根据self.config启动流量生成器
        """

        if self._running:
            raise RuntimeError("SocketTrafficGenerator 已经在运行")

        self._running = True
        self._stop_event = threading.Event()
        self._graph: Graph = self._generate_graph()
        self._runtime_plans: list[_ProcessRuntimePlan] = self._build_runtime_plan(
            self._graph
        )
        self._setup_signal_handlers()

        try:
            self._start_child_processes(self._runtime_plans)
            self._persist_ground_truth(self._graph)
            while not self._stop_event.is_set():
                time.sleep(0.5)
        except KeyboardInterrupt:
            LOGGER.info("traffic generator main loop interrupted, stopping...")
        finally:
            self._stop_event.set()
            self.terminate()
            self._restore_signal_handlers()
            self._running = False

    def terminate(self, timeout: float = 2.0):
        """
        停止流量生成器，优雅退出
        """

        self._stop_event.set()
        deadline = time.time() + timeout
        for process in self._child_processes:
            if not process.is_alive():
                continue
            try:
                os.kill(process.pid, signal.SIGTERM)
            except OSError:
                continue

        for process in self._child_processes:
            remaining = max(0.0, deadline - time.time())
            process.join(timeout=remaining)
            if process.is_alive():
                process.kill()
        self._child_processes.clear()
        self._runtime_plans = []
        LOGGER.info("SocketTrafficGenerator is stopped")

    @staticmethod
    def _worker_entry(config: _WorkerRuntimeConfig):
        """子进程入口：根据配置启动收发线程并响应信号"""

        stop_event = threading.Event()

        def _handle_child_signal(_signum, _frame):
            stop_event.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, _handle_child_signal)
            except ValueError:
                LOGGER.warning("子进程无法注册信号 %s", sig)

        recv_threads = [
            threading.Thread(
                target=SocketTrafficGenerator._receiver_loop,
                args=(sock_cfg, stop_event, f"{config.label}-r{i}"),
                daemon=True,
            )
            for i, sock_cfg in enumerate(config.recv_sockets)
        ]
        send_threads = [
            threading.Thread(
                target=SocketTrafficGenerator._sender_loop,
                args=(
                    target_cfg,
                    stop_event,
                    config.send_interval,
                    config.connection_duration,
                    f"{config.label}-s{i}",
                ),
                daemon=True,
            )
            for i, target_cfg in enumerate(config.send_targets)
        ]

        for thread in [*recv_threads, *send_threads]:
            thread.start()

        try:
            while not stop_event.is_set():
                time.sleep(0.5)
        finally:
            stop_event.set()
            for thread in [*recv_threads, *send_threads]:
                thread.join(timeout=2.0)
            LOGGER.info("[%s] Child process exited", config.label)

    @staticmethod
    def _receiver_loop(
        config: _RecvSocketRuntime, stop_event: threading.Event, label: str
    ):
        """接收线程循环，根据协议选择具体实现"""

        if config.protocol == CONNECTION_TYPE_UDP:
            SocketTrafficGenerator._udp_recv_loop(config, stop_event, label)
        elif config.protocol == CONNECTION_TYPE_TCP:
            SocketTrafficGenerator._tcp_recv_loop(config, stop_event, label)
        else:
            LOGGER.error("[%s] Unsupported protocol: %s", label, config.protocol)

    @staticmethod
    def _sender_loop(
        config: _SendTargetRuntime,
        stop_event: threading.Event,
        interval: float,
        connection_duration: int,
        label: str,
    ):
        """发送线程循环，根据协议向目标源源不断地发送数据"""

        if config.protocol == CONNECTION_TYPE_UDP:
            SocketTrafficGenerator._udp_send_loop(
                config, stop_event, interval, connection_duration, label
            )
        else:
            SocketTrafficGenerator._tcp_send_loop(
                config, stop_event, interval, connection_duration, label
            )

    @staticmethod
    def _tcp_recv_loop(
        config: _RecvSocketRuntime, stop_event: threading.Event, label: str
    ):
        """TCP接收实现，负责accept并持续读取数据"""

        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((config.host, config.port))
        server.listen()
        server.settimeout(1.0)
        LOGGER.info("[%s] TCP Listen at %s:%s", label, config.host, config.port)
        client_threads: list[threading.Thread] = []
        try:
            while not stop_event.is_set():
                try:
                    client, addr = server.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                client_thread = threading.Thread(
                    target=SocketTrafficGenerator._tcp_client_handler,
                    args=(client, addr, stop_event, config, label),
                    daemon=True,
                )
                client_thread.start()
                client_threads.append(client_thread)
        finally:
            server.close()
            LOGGER.info(
                "[%s] TCP Listen stopped %s:%s", label, config.host, config.port
            )
            for thread in client_threads:
                thread.join(timeout=2.0)

    @staticmethod
    def _tcp_client_handler(
        client: socket.socket,
        addr: tuple[str, int],
        stop_event: threading.Event,
        config: _RecvSocketRuntime,
        label: str,
    ):
        """TCP连接数据处理线程，打印来源信息并持续读取"""

        LOGGER.info(
            "[%s] TCP连接建立 %s:%s -> %s:%s",
            label,
            addr[0],
            addr[1],
            config.host,
            config.port,
        )
        client.settimeout(1.0)
        with contextlib.closing(client):
            while not stop_event.is_set():
                try:
                    data = client.recv(4096)
                    if not data:
                        break
                    LOGGER.info(
                        "[%s][PID:%s] recv TCP %s:%s -> %s:%s bytes=%s",
                        label,
                        os.getpid(),
                        addr[0],
                        addr[1],
                        config.host,
                        config.port,
                        len(data),
                    )
                except socket.timeout:
                    continue
                except OSError:
                    break
        LOGGER.info(
            "[%s] TCP连接关闭 %s:%s -> %s:%s",
            label,
            addr[0],
            addr[1],
            config.host,
            config.port,
        )

    @staticmethod
    def _udp_recv_loop(
        config: _RecvSocketRuntime, stop_event: threading.Event, label: str
    ):
        """UDP接收实现，循环读取报文"""

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((config.host, config.port))
        sock.settimeout(1.0)
        LOGGER.info("[%s] UDP Listen at %s:%s", label, config.host, config.port)
        try:
            while not stop_event.is_set():
                try:
                    data, addr = sock.recvfrom(4096)
                    LOGGER.info(
                        "[%s][PID:%s] recv UDP %s:%s -> %s:%s bytes=%s",
                        label,
                        os.getpid(),
                        addr[0],
                        addr[1],
                        config.host,
                        config.port,
                        len(data),
                    )
                except socket.timeout:
                    continue
                except OSError:
                    break
        finally:
            sock.close()
            LOGGER.info(
                "[%s] UDP Listen stopped %s:%s", label, config.host, config.port
            )

    @staticmethod
    def _tcp_send_loop(
        config: _SendTargetRuntime,
        stop_event: threading.Event,
        interval: float,
        connection_duration: int,
        label: str,
    ):
        """TCP发送实现，自动建立连接并周期性发送"""

        payload = (f"ANANSI-{label}" * 100).encode("utf-8")
        per_connection_limit = connection_duration if connection_duration > 0 else None
        while not stop_event.is_set():
            try:
                with socket.create_connection(
                    (config.host, config.port), timeout=2
                ) as sock:
                    sock.settimeout(2.0)
                    sent_cnt = 0
                    while not stop_event.is_set():
                        sock.sendall(payload)
                        sent_cnt += 1
                        if per_connection_limit and sent_cnt >= per_connection_limit:
                            break
                        time.sleep(max(0.01, interval))
            except OSError:
                time.sleep(min(1.0, max(0.01, interval)))

    @staticmethod
    def _udp_send_loop(
        config: _SendTargetRuntime,
        stop_event: threading.Event,
        interval: float,
        connection_duration: int,
        label: str,
    ):
        """UDP发送实现，持续向目标发送数据包"""

        payload = f"ANANSI-{label}".encode("utf-8")
        per_connection_limit = connection_duration if connection_duration > 0 else None
        while not stop_event.is_set():
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.settimeout(1.0)
                sent_cnt = 0
                while not stop_event.is_set():
                    try:
                        sock.sendto(payload, (config.host, config.port))
                        sent_cnt += 1
                        if per_connection_limit and sent_cnt >= per_connection_limit:
                            break
                    except OSError:
                        time.sleep(0.1)
                        continue
                    time.sleep(max(0.01, interval))


def start_generate_traffic(
    config: Optional[SocketTrafficGeneratorConfig] = None,
    log_level: str = "DEBUG",
) -> SocketTrafficGenerator:
    """启动流量生成"""
    LOGGER.setLevel(log_level)
    traffic_generator = SocketTrafficGenerator(config=config)
    traffic_generator.start()
    return traffic_generator


if __name__ == "__main__":
    start_generate_traffic()


__all__ = ["SocketTrafficGenerator", "start_generate_traffic"]
