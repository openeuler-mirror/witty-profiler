"""Socket communication monitoring via kernel instrumentation.

Singleton service that collects socket communication statistics by running
kernel-level sniffers (eBPF or kernel modules) and parsing their output.
Provides query APIs and subscriber notifications for topology graph building.

Architecture:
    - Manages subprocess running C/eBPF socket sniffer binary
    - Parses stdout into pandas DataFrame with standardized columns
    - Maintains in-memory datastore of collected statistics
    - Notifies subscribers of incremental updates
    - Persists to disk for post-collection analysis

Data Collection:
    - Monitors TCP/UDP sockets via kernel instrumentation
    - Non-invasive: No application code modification required
    - Columns include: source IP/port, destination IP/port, protocol, bytes, packets
    - Incremental delivery to subscribers via callbacks

Subscriber Model:
    - Subscribers register callbacks for incremental updates
    - Run in background thread to avoid blocking collection loop
    - Query APIs allow full historical data retrieval

Storage:
    - In-memory DataFrame for fast queries
    - Optional disk persistence (CSV, msgspec binary)
    - Configurable via SnifferConfig

Usage:
    ```python
    # Get singleton monitor
    monitor = get_socket_monitor()
    monitor.start()

    # Query socket statistics
    stats = monitor.query_all_connections()

    # Or through sniffer abstraction
    sniffer = get_socket_sniffer()
    processes = sniffer.query_all_processes()
    ```

Notes:
    Subprocess management includes graceful shutdown on exit.
    Non-blocking I/O used to read sniffer output.
    Thread-safe subscriber notifications.
"""

import atexit
import fcntl
import os
import re
import subprocess
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from subprocess import Popen
from typing import Any, Callable, Final, List

import pandas as pd

from witty_profiler.common.constants import SocketMonitorConstants, SocketSnifferConstants
from witty_profiler.common.env_manager import EnvManager
from witty_profiler.common.logging import get_logger
from witty_profiler.config_manager.config_manager import GlobalConfigManager
from witty_profiler.config_manager.configs import SocketSnifferConfig
from witty_profiler.storage.rotated_file_storage import RotatedFileStorage

LOGGER = get_logger(__name__)


def sniffer_binary_v(binary_path: str):
    results = []
    try:
        binary_path = os.path.abspath(binary_path)
        result = subprocess.run(
            [binary_path, "-v"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        results = list(result.stdout.splitlines())
    except Exception as e:
        LOGGER.error("Failed to get socket sniffer binary version: %s", e)
    return results


def check_binary_compatible(binary_path: str, expected: dict[str, str]) -> bool:
    LOGGER.debug("Checking socket sniffer binary (%s) compatible", binary_path)
    try:
        results = sniffer_binary_v(binary_path)
        if results is None or len(results) == 0:
            raise RuntimeError("No output from socket sniffer binary -v")
        LOGGER.debug("Socket sniffer binary -v output:\n%s", results)
        pattern = re.compile(r"^(?P<key>\w+):(?P<value>\w+) \((?P<code>\w+)\)$")
        compatible = True
        for line in results:
            key, value, code = pattern.match(line).groupdict().values()
            if key in expected:
                expected_value = expected[key]
                key_compatible = value == expected_value
                LOGGER.debug(
                    "[%s] %s = %s : %s",
                    key,
                    value,
                    expected_value,
                    key_compatible,
                )
                compatible &= key_compatible
    except RuntimeError as e:
        LOGGER.error("Failed to verify socket sniffer binary: %s", e)
        return False
    LOGGER.info("Socket sniffer binary compatibility check result: %s", compatible)
    return compatible


class MonitorColumn:
    """
    Columns in the socket monitor dataframe
    """

    FUNCTION: Final[str] = "function"
    LOCAL_PID: Final[str] = "local_pid"
    LOCAL_TID: Final[str] = "local_tid"
    LOCAL_ADDR: Final[str] = "local_addr"
    LOCAL_PORT: Final[str] = "local_port"
    REMOTE_ADDR: Final[str] = "remote_addr"
    REMOTE_PORT: Final[str] = "remote_port"
    START_TIME: Final[str] = "start_time"
    END_TIME: Final[str] = "end_time"
    DATA_SIZE_TOTAL: Final[str] = "data_size_total"
    PACKET_CNT: Final[str] = "packet_cnt"


MONITOR_NON_STAT_COLUMNS: Final[list[str]] = [
    MonitorColumn.FUNCTION,
    MonitorColumn.LOCAL_PID,
    MonitorColumn.LOCAL_TID,
    MonitorColumn.LOCAL_ADDR,
    MonitorColumn.LOCAL_PORT,
    MonitorColumn.REMOTE_ADDR,
    MonitorColumn.REMOTE_PORT,
]
MONITOR_STAT_COLUMNS: Final[list[str]] = [
    MonitorColumn.START_TIME,
    MonitorColumn.END_TIME,
    MonitorColumn.DATA_SIZE_TOTAL,
    MonitorColumn.PACKET_CNT,
]

MONITOR_COLUMNS: Final[list[str]] = [*MONITOR_NON_STAT_COLUMNS, *MONITOR_STAT_COLUMNS]


@dataclass
class SocketSubscribeOption:
    push_minimum_interval: float = 1.0  # seconds


class SocketMonitor(ABC):

    _instance = None
    _lock = threading.Lock()  # 用于线程安全的单例（同一进程内）
    _process_lock_fd = None  # 跨进程锁的文件描述符

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    # 尝试获取跨进程锁
                    lock_fd = cls._acquire_process_lock()
                    if lock_fd is None:
                        raise RuntimeError(
                            f"Another instance of {cls.__name__} is already running."
                        )

                    instance = super().__new__(cls)
                    instance._init(lock_fd)
                    cls._instance = instance
        return cls._instance

    @classmethod
    def get_instance(cls) -> "SocketMonitor":
        """获取单例实例"""
        if cls._instance is None:
            cls()
        return cls._instance

    @classmethod
    def _acquire_process_lock(cls) -> int | None:
        """尝试获取跨进程排他锁，成功返回 fd，失败返回 None"""
        try:
            fd = os.open(
                SocketMonitorConstants.LOCK_FILE(), os.O_CREAT | os.O_RDWR, 0o644
            )
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)  # 非阻塞排他锁
            return fd
        except (IOError, OSError):
            # 另一个进程已持有锁
            if "fd" in locals():
                os.close(fd)
            return None

    def _init(self, lock_fd: int):

        self._process_lock_fd = lock_fd
        self._subscribers: dict[str, Callable[[pd.DataFrame]]] = {}
        self._data_buffer: List = []
        self._data_buffer_size: int = 0
        self._running = False
        self._sniffer_proc = None
        self._reader_thread = None

        mngr: GlobalConfigManager = GlobalConfigManager.get_instance()
        self._config: SocketSnifferConfig = (
            mngr.get_config().sniffer_config.socket_sniffer
        )

        self._data_file = mngr.convert_to_tmp_path(self._config.data_file_path)
        self._storage = RotatedFileStorage(
            log_file_path_prefix=self._data_file,
            max_size_in_mb=self._config.maximum_log_file_size_in_mb,
            max_rotation_cnt=self._config.maximum_rotation_cnt,
        )
        os.makedirs(os.path.dirname(self._data_file), exist_ok=True)

        # 注册退出清理
        atexit.register(self._cleanup)

    @abstractmethod
    def _msg_type_compatible(self, msg_type: str) -> bool:
        """判断 msg 是否兼容"""
        raise NotImplementedError

    def _start_sniffer(self):
        if self._sniffer_proc is not None and self._sniffer_proc.poll() is None:
            return
        mngr: GlobalConfigManager = GlobalConfigManager.get_instance()
        binary_path: str = (
            mngr.get_config().sniffer_config.socket_sniffer.socket_sniffer_binary_path
        )
        LOGGER.info(
            "Starting socket sniffer binary: %s",
            binary_path,
        )
        self._sniffer_proc = subprocess.Popen(
            [binary_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,  # 无缓冲或行缓冲
            text=False,  # 以 bytes 读取更安全
        )
        LOGGER.info("Socket sniffer binary started. (PID: %s)", self._sniffer_proc.pid)

    def _start_reader_thread(self):
        if self._reader_thread is not None and self._reader_thread.is_alive():
            return
        self._reader_thread = threading.Thread(target=self._read_output, daemon=True)
        self._reader_thread.start()

    def _start(self):
        """启动采集进程与读取线程，避免重入"""
        if self._running:
            LOGGER.info("SocketMonitor already running, skip start.")
            return
        self._running = True
        # 启动前检查
        mngr = GlobalConfigManager.get_instance()
        socket_sniffer_config = mngr.get_config().sniffer_config.socket_sniffer

        if not check_binary_compatible(
            binary_path=socket_sniffer_config.socket_sniffer_binary_path,
            expected={"flow_dump_style": socket_sniffer_config.msg_style},
        ):
            raise RuntimeError("Socket sniffer binary verification failed.")

        self._start_sniffer()
        self._start_reader_thread()
        LOGGER.info("Socket monitor started.")

    def _stop(self, wait: bool = True, timeout: float = 5.0):
        """停止采集进程与读取线程"""
        if not self._running and self._sniffer_proc is None:
            return
        LOGGER.info("Stopping socket monitor...")
        self._running = False
        if self._sniffer_proc is not None:
            LOGGER.info("Stopping sniffer process...")
            try:
                self._sniffer_proc.terminate()
                if wait:
                    self._sniffer_proc.wait(timeout=timeout)
            except Exception as e:
                LOGGER.warning("Failed to stop sniffer process: %s", e)
            LOGGER.info(
                "Sockets sniffer process poll status: %s", self._sniffer_proc.poll()
            )
        if self._reader_thread is not None and wait:
            self._reader_thread.join(timeout=timeout)
            LOGGER.info(
                "Socket reader thread join status: alive=%s",
                self._reader_thread.is_alive(),
            )
            self._reader_thread = None
        if wait:
            self._sniffer_proc = None
        # reset buffer
        self._data_buffer = []
        LOGGER.info("Socket monitor stopped.")

    def _read_output(self):
        """持续读取子进程 stdout，解析并分发"""
        config = GlobalConfigManager().get_config().sniffer_config.socket_sniffer
        entry_buffer_size = config.entry_buffer_size
        report_interval_ms = config.monitor_report_maximum_interval_by_second * 1e3
        last_report_time = time.time()
        report_cnt = 0

        while self._running and self._sniffer_proc.poll() is None:
            line = self._read_next_message(self._sniffer_proc)
            if not line:  # broken pipe
                LOGGER.info("Socket sniffer recv: broken pipe or no data.")
                break
            try:
                line_data = self._on_recv_line(line)
                self._data_buffer.append(line_data)
                self._data_buffer_size += 1

                if (
                    self._data_buffer_size >= entry_buffer_size
                    or (time.time() - last_report_time) * 1e3 >= report_interval_ms
                ):
                    # TODO: 用一个单独的处理线程进行数据落盘和分发，避免阻塞读取线程
                    LOGGER.debug(
                        "[report %s] Flushing data buffer with %d entries.",
                        report_cnt,
                        self._data_buffer_size,
                    )
                    report_cnt += 1
                    df = self._convert_buffer_to_dataframe(self._data_buffer)
                    self._data_buffer = []  # reset buffer
                    self._data_buffer_size = 0
                    self._append_to_disk(df)
                    self._notify_subscribers(df)
                    last_report_time = time.time()
            except Exception as e:
                LOGGER.warning("Parse error: %s", e)
                # TODO: debug raise
                raise e

        # 子进程退出后清理
        self._running = False

    @abstractmethod
    def _read_next_message(self, proc: Popen[bytes]) -> bytes:
        """读取下一个完整消息"""
        raise NotImplementedError

    @abstractmethod
    def _on_recv_line(self, line: bytes) -> Any:
        """处理接收到的一行数据"""
        raise NotImplementedError

    @abstractmethod
    def _convert_buffer_to_dataframe(self, buffer: list) -> pd.DataFrame:
        """将行数据转换为 DataFrame"""
        raise NotImplementedError

    def clear_disk_storage(self):
        """清理落盘的数据文件"""
        self._storage.clear_all()

    def _append_to_disk(self, df: pd.DataFrame):
        """将新数据追加到磁盘文件"""
        with self._storage as fd:
            df.to_csv(
                fd,
                header=False,
                index=False,
            )

    def register_subscriber(
        self,
        name: str,
        callback: Callable[[pd.DataFrame], None],
        enable_override: bool = False,
    ):
        """注册订阅者，接收增量数据；首次注册时启动采集"""
        if name in self._subscribers:
            if not enable_override:
                raise ValueError("Subscriber %s already exists.", name)
            LOGGER.warning("Subscriber %s already exists, overwriting.", name)
            self.unregister_subscriber(name)
        LOGGER.info("Register subscriber %s.", name)
        self._subscribers[name] = callback
        if not self._running:
            self._start()

    def unregister_subscriber(self, name: str):
        """注销订阅者；无订阅者时停止采集"""
        self._subscribers.pop(name, None)
        if not self._subscribers:
            self._stop()

    def _notify_subscribers(self, df: pd.DataFrame):
        """通知所有订阅者"""
        for name, callback in self._subscribers.items():
            callback(df)

    def get_full_data(self) -> pd.DataFrame:
        """提供全量数据查询接口"""
        if os.path.exists(self._data_file):
            try:
                return pd.read_csv(self._data_file, header=MONITOR_COLUMNS)
            except (OSError, ValueError, IOError) as e:
                LOGGER.error("Failed to read csv data file: %s", e)
        else:
            LOGGER.error("Data file %s does not exist.", self._data_file)
        return pd.DataFrame()

    def _cleanup(self):
        """清理资源：释放锁、终止子进程、删除锁文件（可选）"""
        self._stop(wait=True, timeout=5.0)
        if self._process_lock_fd is not None:
            fcntl.flock(self._process_lock_fd, fcntl.LOCK_UN)
            os.close(self._process_lock_fd)
            # 锁文件的存在与否不重要，关键是 flock 是否被持有


class SocketMonitorByCSV(SocketMonitor):
    """
    按照csv字符串传输 的 SocketMonitor
    """

    def _msg_type_compatible(self, msg_type: str) -> bool:
        return msg_type == SocketSnifferConstants.SOCKET_SNIFFER_MSG_CSV

    def _read_next_message(self, proc: subprocess.Popen[bytes]) -> bytes:
        return proc.stdout.readline()

    def _on_recv_line(self, line: bytes) -> Any:
        item = line.decode("utf-8").strip().split(",")
        return item

    def _convert_buffer_to_dataframe(self, buffer):
        if len(buffer) == 0:  # 忽略空行
            return pd.DataFrame()
        if not hasattr(self, "_column_names") or self._column_names is None:
            self._column_names = buffer[0]
            self._column_names = [name.strip() for name in self._column_names]
            buffer = buffer[1:]
        return pd.DataFrame(buffer, columns=self._column_names)


if EnvManager().msgspec_compatible():
    import msgspec

    class SocketEvent(msgspec.Struct):
        function: str
        local_pid: int
        local_tid: int
        local_addr: str
        local_port: int
        remote_addr: str
        remote_port: int
        start_time: int
        end_time: int
        data_size_total: int
        packet_cnt: int

    class SocketMonitorByMsgSpec(SocketMonitor):
        """
        基于 msgspec 的 SocketMonitor
        """

        def __init__(self):
            super().__init__()
            self.msgspec_decoder = msgspec.msgpack.Decoder(SocketEvent)

        def _msg_type_compatible(self, msg_type: str) -> bool:
            return msg_type == SocketSnifferConstants.SOCKET_SNIFFER_MSG_MSGSPEC

        def _read_next_message(self, proc: subprocess.Popen[bytes]) -> bytes:
            size_bytes = proc.stdout.read(4)
            if not size_bytes:
                return b""
            msg_len = int.from_bytes(size_bytes, "big")
            if msg_len <= 0:
                return b""
            return proc.stdout.read(msg_len)

        def _on_recv_line(self, line: bytes) -> Any:
            return self.msgspec_decoder.decode(line)

        def _convert_buffer_to_dataframe(
            self, buffer: list[SocketEvent]
        ) -> pd.DataFrame:
            """将行数据高效转换为 DataFrame"""
            if not buffer:
                return pd.DataFrame(columns=MONITOR_COLUMNS)
            return pd.DataFrame.from_records(buffer, columns=MONITOR_COLUMNS)


def get_socket_monitor() -> SocketMonitor:
    """获取 SocketMonitor 实例"""
    if (
        EnvManager().msgspec_compatible()
        and GlobalConfigManager().get_config().sniffer_config.socket_sniffer.msg_style
        == SocketSnifferConstants.SOCKET_SNIFFER_MSG_MSGSPEC
    ):
        return SocketMonitorByMsgSpec.get_instance()
    return SocketMonitorByCSV.get_instance()


__all__ = ["get_socket_monitor"]
