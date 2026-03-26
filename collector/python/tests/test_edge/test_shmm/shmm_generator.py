"""Shared-memory graph construction and smoke test utilities."""

from __future__ import annotations

import json
import math
import multiprocessing
import os
import signal
import threading
import time
import uuid
from dataclasses import dataclass
from multiprocessing import Process
from multiprocessing.shared_memory import SharedMemory
from queue import Empty
from typing import Dict, Iterable, List, Sequence

from witty_profiler.common.logging import get_logger
from witty_profiler.edge.structual.belong import AccessEdge
from witty_profiler.entity.node_entity import ProcessEntity, SharedMemoryEntity
from witty_profiler.graph.graph import Graph

LOGGER = get_logger(__name__)


@dataclass(frozen=True)
class SharedMemoryAssignment:
    shm_name: str
    size: int
    role: str  # "writer" or "reader"
    is_creator: bool = False


def construct_shmm_graph(
    num_processes: int,
    connection_probability: float,
) -> Graph:
    """
    构建共享内存管理系统的图结构

    该函数创建一个包含指定数量进程节点的图，并根据给定的连接概率随机生成进程间的共享内存边连接。

    Args:
        num_processes (int): 进程节点的数量
        connection_probability (float): 进程间建立连接的概率值，范围在0到1之间

    Returns:
        Graph: 包含进程节点和共享内存边的图对象
    """
    import random

    from witty_profiler.edge.edge import EdgeFactory
    from witty_profiler.entity.entity_base import EntityFactory
    from witty_profiler.graph.graph import Graph

    # 获取实体工厂和边工厂实例
    ent_fact = EntityFactory.get_instance()
    edg_fact = EdgeFactory.get_instance()

    # 创建指定数量的进程实体节点
    processes = [ent_fact.create_entity(ProcessEntity()) for i in range(num_processes)]

    edges = []
    # 遍历所有可能的进程对组合，根据连接概率创建边
    for i in range(num_processes):
        for j in range(i + 1, num_processes):
            if random.random() < connection_probability:
                shared_memory = SharedMemoryEntity.create_ensure_unique_id(
                    shm_name="witty_profiler_shm_{}_{}_{}".format(
                        i, j, uuid.uuid4().hex[:8]
                    ),
                    shm_size=4096,
                )
                edge = AccessEdge(source_node=processes[i], target_node=shared_memory)
                edges.append(edge)
                edge = AccessEdge(source_node=processes[j], target_node=shared_memory)
                edges.append(edge)
    # 构建并返回图对象
    graph = Graph(nodes=processes, edges=edges)
    LOGGER.info("Constructed SHMM graph: \n%s", graph.describe())
    return graph


def _build_payload(edge_id: str, round_idx: int, max_size: int) -> bytes:
    payload = f"{edge_id}:{round_idx}".encode()
    if len(payload) > max_size:
        payload = payload[:max_size]
    return payload


def wait_for_condition(predicate, timeout: float, step: float) -> bool:
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        if predicate():
            return True
        time.sleep(step)
    return False


def _reader_thread_func(
    shm: SharedMemoryEntity,
    stop_event: threading.Event,
    assignment: SharedMemoryAssignment,
    thread_id: str,
    interval: float,
    cnt: int,
):
    # 等待可读
    if wait_for_condition(
        lambda: shm.buf[0] != 0 or stop_event.is_set(),
        timeout=interval,
        step=interval / 10,
    ):
        if stop_event.is_set():
            raise KeyboardInterrupt()
        cnt += 1
        data = shm.buf.tobytes().decode().rstrip("\x00")
        LOGGER.info(
            "[PID:%s]Thread %s: read from %s: %s",
            os.getpid(),
            thread_id,
            assignment.shm_name,
            len(data),
        )
        shm.buf[0] = 0
        time.sleep(interval)


def _writer_thread_func(
    shm: SharedMemory,
    stop_event: threading.Event,
    assignment: SharedMemoryAssignment,
    thread_id: str,
    interval: float,
    cnt: int,
):
    # 等待可写
    if wait_for_condition(
        lambda: shm.buf[0] == 0 or stop_event.is_set(),
        timeout=interval,
        step=interval / 10,
    ):
        if stop_event.is_set():
            raise KeyboardInterrupt()
        payload = _build_payload(
            edge_id=assignment.shm_name,
            round_idx=cnt,
            max_size=assignment.size,
        )
        LOGGER.info(
            "Thread %s: write to %s: %s",
            thread_id,
            assignment.shm_name,
            len(payload),
        )
        shm.buf[: len(payload)] = payload
        time.sleep(interval)
    return


def _shm_worker_rw_thread(
    thread_id: str,
    assignment: SharedMemoryAssignment,
    rounds: int,
    interval: float,
    stop_event: threading.Event,
) -> None:
    """
    写任务线程：每隔interval时间间隔唤醒，写入payload到共享内存区域（如果没清理则跳过）

    Args:
        thread_id: 线程的唯一标识符
        assignment: 共享内存分配任务，包含需要操作的共享内存区域信息
        rounds: 每个分配任务需要执行的轮次数量
        interval: 每轮操作之间的间隔时间（秒）
        stop_event: 停止事件，用于控制线程的运行

    Returns:
        None
    """
    LOGGER.info("%s Thread %s: start", assignment.role, thread_id)
    cnt = 0
    shm: SharedMemory = None
    if rounds <= 0:
        rounds = math.inf
    try:
        while cnt < rounds and not stop_event.is_set():
            cnt += 1
            # 创建/访问共享内存
            if shm is None:
                try:
                    shm = SharedMemory(
                        name=assignment.shm_name,
                        size=assignment.size if assignment.is_creator else 0,
                        create=assignment.is_creator,
                    )
                    LOGGER.info(
                        "%s access shm %s (creater:%s)",
                        thread_id,
                        assignment.shm_name,
                        assignment.is_creator,
                    )
                except FileNotFoundError:
                    time.sleep(interval / 10)
                    continue
                except ValueError:
                    LOGGER.debug(
                        "%s (role: %s) encountered value error when accessing shm",
                        thread_id,
                        assignment.role,
                    )
                    continue
                continue
            if assignment.role == "reader":
                _reader_thread_func(
                    shm=shm,
                    stop_event=stop_event,
                    assignment=assignment,
                    thread_id=thread_id,
                    interval=interval,
                    cnt=cnt,
                )
            else:
                _writer_thread_func(
                    shm=shm,
                    stop_event=stop_event,
                    assignment=assignment,
                    thread_id=thread_id,
                    interval=interval,
                    cnt=cnt,
                )
        LOGGER.info("Thread %s executed gracefully", thread_id)
    except KeyboardInterrupt:  # pragma: no cover - diagnostic path
        LOGGER.info("Thread %s interrupted", thread_id)
    finally:
        LOGGER.info("Thread %s: cleaning up", thread_id)
        try:
            if shm:
                try:
                    if assignment.is_creator:
                        LOGGER.info(
                            "Shm creator %s cleaning up shm:%s",
                            thread_id,
                            assignment.shm_name,
                        )
                        shm.close()
                        shm.unlink()
                    else:
                        LOGGER.info(
                            "Shm non-creator %s cleaning up shm:%s",
                            thread_id,
                            assignment.shm_name,
                        )
                        # fork创建时，告诉 resource_tracker “这不是我创建的”，避免错误清理
                        shm.close()
                        if multiprocessing.get_start_method() == "fork":
                            from multiprocessing import resource_tracker

                            resource_tracker.unregister(shm._name, "shared_memory")
                        # shm.unlink()
                    del shm
                except Exception as e:
                    LOGGER.info(
                        "Exception during resource_tracker.unregister for %s ", shm.name
                    )

            LOGGER.info("Thread %s: cleaned up", thread_id)
        except (
            FileNotFoundError,
            KeyboardInterrupt,
        ) as e:  # pragma: no cover - diagnostic path
            LOGGER.info("Exception during shm cleanup: %s", e)
            pass
        LOGGER.info("%s Thread %s done", assignment.role, thread_id)


def _shm_worker_clean_up(
    assignments: Iterable[SharedMemoryAssignment],
    threads: list[threading.Thread],
    stop_event: threading.Event,
) -> None:
    stop_event.set()
    for thread in threads:
        thread.join(timeout=1)
    for assignment in assignments:
        try:
            shm = SharedMemory(name=assignment.shm_name, create=False)
            shm.close()
            # shm.unlink()
        except (
            FileNotFoundError,
            KeyboardInterrupt,
            KeyError,
        ):  # pragma: no cover - diagnostic path
            pass


def _shm_worker(
    worker_id: str,
    assignments: Sequence[SharedMemoryAssignment],
    rounds: int,
    interval: float,
) -> None:
    """
    执行共享内存读写工作的工作者进程。
    对每个读或者写assignment, 启动一个线程来处理。
    读任务线程：监听共享内存区域是否有写入，有则读取并清理
    写任务线程：每隔interval时间间隔唤醒，写一次payload到共享内存区域（如果没清理则跳过）

    Args:
        worker_id: 工作者进程的唯一标识符
        assignments: 共享内存分配任务序列，包含需要操作的共享内存区域信息
        rounds: 每个分配任务需要执行的轮次数量
        interval: 每轮操作之间的间隔时间（秒）

    Returns:
        None
    """
    signal.signal(signal.SIGTERM, signal.default_int_handler)
    threads = []
    stop_event = threading.Event()
    try:
        LOGGER.info(
            "Worker %s started with assignments %s",
            worker_id,
            [assignment.role for assignment in assignments],
        )
        for ti, assignment in enumerate(assignments):
            thread = threading.Thread(
                target=_shm_worker_rw_thread,
                args=(
                    f"{worker_id}-t{ti}",
                    assignment,
                    rounds,
                    interval,
                    stop_event,
                ),
                name=f"{worker_id}-t{ti}",
            )
            thread.start()
            threads.append(thread)
        # 等待结束
        while not all([not thread.is_alive() for thread in threads]):
            LOGGER.info(
                f"[PID:{os.getpid()}]Worker {worker_id} waiting for threads to finish"
            )
            time.sleep(interval * 10)
        LOGGER.info("Worker %s all threads done", worker_id)
    except KeyboardInterrupt:  # pragma: no cover - diagnostic path
        try:
            LOGGER.info("Worker %s interrupted", worker_id)
            rounds = -1
            stop_event.set()
        except KeyboardInterrupt:  # pragma: no cover - diagnostic path
            stop_event.set()
    finally:
        # clear threads
        try:
            _shm_worker_clean_up(assignments, threads, stop_event)
        except KeyboardInterrupt:  # pragma: no cover - diagnostic path
            _shm_worker_clean_up(assignments, threads, stop_event)
        LOGGER.info("Worker %s done", worker_id)


def _setup_shared_memory_assignments(
    graph: Graph,
) -> Dict[str, List[SharedMemoryAssignment]]:
    """
    为图中的共享内存边设置共享内存段

    参数:
        graph (Graph): 包含进程节点和边的图结构，其中共享内存边需要创建对应的共享内存段

    返回:
        Dict[str, List[SharedMemoryAssignment]]:
        - 字典，键为进程全局ID(此时非PID)，值为该进程的共享内存分配列表
    """
    assignments: Dict[str, List[SharedMemoryAssignment]] = {}
    visited_shmm = set()

    for idx, edge in enumerate(graph.edges):
        # 选择共享内存边
        if not isinstance(edge, AccessEdge):
            continue
        if len(edge.nodes) != 2:
            continue
        process_node, shm_node = edge.nodes
        if not isinstance(process_node, ProcessEntity):
            continue
        if not isinstance(shm_node, SharedMemoryEntity):
            continue

        is_writer = shm_node.shm_name not in visited_shmm
        assignments.setdefault(process_node.global_id, []).append(
            SharedMemoryAssignment(
                shm_name=shm_node.shm_name,
                size=shm_node.shm_size,
                role="writer" if is_writer else "reader",
                is_creator=is_writer,
            )
        )
        visited_shmm.add(shm_node.shm_name)
    return assignments


def _cleanup_shm_segments(graph: Graph) -> None:
    LOGGER.info("Cleaning up SHM segments")
    for node in graph.nodes:
        if isinstance(node, SharedMemoryEntity):
            try:
                shm = SharedMemory(name=node.shm_name, create=False)
                shm.close()
                # shm.unlink()
            except (FileNotFoundError, KeyError):
                LOGGER.info("SHM %s already cleaned up", node.shm_name)


def run_shared_memory_round_trip(
    graph: Graph, rounds: int, interval: float, graph_file_path: str
) -> List[dict]:
    signal.signal(signal.SIGTERM, signal.default_int_handler)
    if not graph.edges:
        LOGGER.warning(
            "Graph has no shared memory edges; skipping round-trip simulation"
        )
        return []
    try:
        multiprocessing.set_start_method("fork")
    except RuntimeError:
        pass

    assignments: Dict[str, List[SharedMemoryAssignment]] = (
        _setup_shared_memory_assignments(graph)
    )

    processes: List[Process] = []

    try:
        for i, process_node in enumerate(graph.nodes):
            if not isinstance(process_node, ProcessEntity):
                continue

            node_assignments = assignments.get(process_node.global_id, [])
            proc = Process(
                target=_shm_worker,
                args=(
                    f"w{i}",  # process node index
                    node_assignments,
                    rounds,
                    interval,
                ),
                name=f"shmm-worker-{i}",
            )
            proc.start()
            if proc.pid:
                LOGGER.info(
                    "Started SHMM worker process %s with PID %d", proc.name, proc.pid
                )
                process_node.pid = proc.pid
            processes.append(proc)

        # 打印图
        os.makedirs(os.path.dirname(graph_file_path), exist_ok=True)
        with open(
            os.path.join(os.path.dirname(graph_file_path), "ground_truth.log"), "w"
        ) as f:
            f.write(graph.describe())
        with open(graph_file_path, "w") as f:
            f.write(json.dumps(graph.model_dump(), indent=2))

        if not processes:
            LOGGER.warning(
                "No processes attached to shared memory edges; nothing to simulate"
            )
            return []
        while any([proc.is_alive() for proc in processes]):
            time.sleep(interval)
        LOGGER.info("All SHMM worker processes done")
    except KeyboardInterrupt:  # pragma: no cover - diagnostic path
        LOGGER.info("SHMM simulation interrupted")
    finally:
        LOGGER.info("Cleaning up SHMM worker processes")
        for proc in processes:
            if proc.is_alive():
                LOGGER.info("Interrupting process %s", proc.name)
                os.kill(proc.pid, signal.SIGINT)
        for proc in processes:
            proc.join(timeout=1)
        for proc in processes:
            if proc.is_alive():
                LOGGER.warning(
                    "Process %s is still alive, try to terminate it", proc.name
                )
                proc.terminate()
                LOGGER.warning("Process %s is alive: %s", proc.name, proc.is_alive())
            proc.join(timeout=1)
        _cleanup_shm_segments(graph)


def parse_args(argv: Sequence[str] | None = None):
    import argparse

    parser = argparse.ArgumentParser(description="Test SHMM graph construction")
    parser.add_argument(
        "--num-processes",
        type=int,
        default=3,
        help="Number of processes to simulate",
    )
    parser.add_argument(
        "--connection-probability",
        type=float,
        default=1,
        help="Probability of connection between processes",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=0,
        help="How many read/write cycles to execute per shared memory edge. (0 for infinite)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1,
        help="Delay between read/write operations (seconds)",
    )
    return parser.parse_args(argv)


def shmm_graph_start(
    num_processes: int,
    connection_probability: float,
    graph_file_path: str,
    rounds: int,
    interval: float,
) -> None:
    graph: Graph = construct_shmm_graph(
        num_processes=num_processes,
        connection_probability=connection_probability,
    )

    run_shared_memory_round_trip(
        graph,
        rounds=rounds,
        interval=interval,
        graph_file_path=graph_file_path,
    )


if __name__ == "__main__":
    cli_args = parse_args()
    graph_file_path = os.path.join(
        os.path.dirname(__file__), "local", "ground_truth.json"
    )
    shmm_graph_start(
        num_processes=cli_args.num_processes,
        connection_probability=cli_args.connection_probability,
        graph_file_path=graph_file_path,
        rounds=cli_args.rounds,
        interval=cli_args.interval,
    )
