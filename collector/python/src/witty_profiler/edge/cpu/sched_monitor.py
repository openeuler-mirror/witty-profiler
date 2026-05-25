"""Monitor scheduler runtime data from the sched monitor binary.

Provides a singleton service that runs the sched monitor binary, parses its
output (CSV or msgspec), buffers records, persists to disk, and notifies
subscribers with incremental updates.

Notes:
        - Only Linux environments are supported (uses fcntl and eBPF tooling).
        - Output format is validated via the binary's `-v` output.

注意事项:
        - 无
"""

import atexit
import fcntl
import os
import re
import subprocess
import threading
import time
from abc import ABC, abstractmethod
from subprocess import Popen
from typing import Any, Callable, Final, List

import pandas as pd

from witty_profiler.common.constants import (
    CacheSnifferConstants,
    SchedMonitorColumn,
    SchedMonitorConstants,
    TimeConstants,
)
from witty_profiler.common.env_manager import EnvManager
from witty_profiler.common.logging import get_logger
from witty_profiler.config_manager.config_manager import GlobalConfigManager
from witty_profiler.config_manager.configs import CPUSnifferConfig
from witty_profiler.storage.rotated_file_storage import RotatedFileStorage

LOGGER = get_logger(__name__)


def sched_monitor_binary_v(binary_path: str) -> list[str]:
    results: list[str] = []
    try:
        binary_path = os.path.abspath(binary_path)
        result = subprocess.run(
            [binary_path, "-v"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        results = list(result.stdout.splitlines())
    except Exception as exc:  # pragma: no cover - best effort
        LOGGER.error("Failed to get sched monitor binary version: %s", exc)
    return results


def check_binary_compatible(binary_path: str, expected: dict[str, str]) -> bool:
    LOGGER.debug("Checking sched monitor binary (%s) compatible", binary_path)
    try:
        results = sched_monitor_binary_v(binary_path)
        if not results:
            raise RuntimeError("No output from sched monitor binary -v")
        LOGGER.debug("Sched monitor binary -v output:\n%s", results)
        pattern = re.compile(r"^(?P<key>\w+):(?P<value>\w+) \((?P<code>\w+)\)$")
        compatible = True
        for line in results:
            match = pattern.match(line)
            if not match:
                continue
            key, value, _code = match.groupdict().values()
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
    except RuntimeError as exc:
        LOGGER.error("Failed to verify sched monitor binary: %s", exc)
        return False
    LOGGER.info("Sched monitor binary compatibility check result: %s", compatible)
    return compatible


SCHED_MONITOR_COLUMNS: Final[list[str]] = SchedMonitorColumn.columns()
SCHED_MONITOR_RAW_COLUMNS: Final[list[str]] = [
    SchedMonitorColumn.PID,
    SchedMonitorColumn.TGID,
    SchedMonitorColumn.CPU,
    SchedMonitorColumn.TIME_NS,
]


class SchedMonitor(ABC):
    """Singleton service for scheduler runtime monitoring."""

    _instance = None
    _lock = threading.Lock()
    _process_lock_fd = None

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
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
    def get_instance(cls) -> "SchedMonitor":
        if cls._instance is None:
            cls()
        return cls._instance

    @classmethod
    def _acquire_process_lock(cls) -> int | None:
        try:
            fd = os.open(SchedMonitorConstants.LOCK_FILE(), os.O_CREAT | os.O_RDWR, 0o644)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fd
        except (IOError, OSError):
            if "fd" in locals():
                os.close(fd)
            return None

    def _init(self, lock_fd: int):
        self._process_lock_fd = lock_fd
        self._subscribers: dict[str, Callable[[pd.DataFrame], None]] = {}
        self._data_buffer: List = []
        self._data_buffer_size: int = 0
        self._running = False
        self._monitor_proc: Popen[bytes] | None = None
        self._reader_thread: threading.Thread | None = None

        mngr: GlobalConfigManager = GlobalConfigManager.get_instance()
        self._config: CPUSnifferConfig = mngr.get_config().sniffer_config.cpu_sniffer

        self._data_file = mngr.convert_to_tmp_path(self._config.sched_data_file_path)
        self._storage = RotatedFileStorage(
            log_file_path_prefix=self._data_file,
            max_size_in_mb=self._config.maximum_log_file_size_in_mb,
            max_rotation_cnt=self._config.maximum_rotation_cnt,
        )
        data_dir = os.path.dirname(self._data_file)
        if data_dir:
            os.makedirs(data_dir, exist_ok=True)

        atexit.register(self._cleanup)

    @abstractmethod
    def _msg_type_compatible(self, msg_type: str) -> bool:
        """Return True if the output style matches this monitor."""

    def _start_sniffer(self):
        if self._monitor_proc is not None and self._monitor_proc.poll() is None:
            return
        mngr: GlobalConfigManager = GlobalConfigManager.get_instance()
        binary_path: str = (
            mngr.get_config().sniffer_config.cpu_sniffer.cpu_sched_monitor_binary_path
        )
        LOGGER.info("Starting sched monitor binary: %s", binary_path)
        self._monitor_proc = subprocess.Popen(
            [binary_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            text=False,
        )
        LOGGER.info("Sched monitor binary started. (PID: %s)", self._monitor_proc.pid)

    def _start_reader_thread(self):
        if self._reader_thread is not None and self._reader_thread.is_alive():
            return
        self._reader_thread = threading.Thread(target=self._read_output, daemon=True)
        self._reader_thread.start()

    def _start(self):
        if self._running:
            LOGGER.info("SchedMonitor already running, skip start.")
            return
        self._running = True

        mngr: GlobalConfigManager = GlobalConfigManager.get_instance()
        cpu_sniffer_config = mngr.get_config().sniffer_config.cpu_sniffer
        if not check_binary_compatible(
            binary_path=cpu_sniffer_config.cpu_sched_monitor_binary_path,
            expected={"output_style": cpu_sniffer_config.msg_style},
        ):
            raise RuntimeError("Sched monitor binary verification failed.")

        self._start_sniffer()
        self._start_reader_thread()
        LOGGER.info("Sched monitor started.")

    def _stop(self, wait: bool = True, timeout: float = 5.0):
        if not self._running and self._monitor_proc is None:
            return
        LOGGER.info("Stopping sched monitor...")
        self._running = False
        if self._monitor_proc is not None:
            LOGGER.info("Stopping sched monitor process...")
            try:
                self._monitor_proc.terminate()
                if wait:
                    self._monitor_proc.wait(timeout=timeout)
            except Exception as exc:
                LOGGER.warning("Failed to stop sched monitor process: %s", exc)
            LOGGER.info(
                "Sched monitor process poll status: %s", self._monitor_proc.poll()
            )
        if self._reader_thread is not None and wait:
            self._reader_thread.join(timeout=timeout)
            LOGGER.info(
                "Sched monitor reader thread join status: alive=%s",
                self._reader_thread.is_alive(),
            )
            self._reader_thread = None
        if wait:
            self._monitor_proc = None
        self._data_buffer = []
        LOGGER.info("Sched monitor stopped.")

    def _read_output(self):
        config = GlobalConfigManager().get_config().sniffer_config.cpu_sniffer
        entry_buffer_size = config.entry_buffer_size
        report_interval_ms = config.monitor_report_maximum_interval_by_second * 1e3
        last_report_time = time.time()
        window_start_ns = time.time_ns()
        report_cnt = 0

        while self._running and self._monitor_proc.poll() is None:
            line = self._read_next_message(self._monitor_proc)
            if not line:
                LOGGER.info("Sched monitor recv: broken pipe or no data.")
                break
            try:
                line_data = self._on_recv_line(line)
                if line_data is None:
                    continue
                self._data_buffer.append(line_data)
                self._data_buffer_size += 1

                if (
                    self._data_buffer_size >= entry_buffer_size
                    or (time.time() - last_report_time) * 1e3 >= report_interval_ms
                ):
                    window_end_ns = time.time_ns()
                    LOGGER.debug(
                        "[report %s] Flushing data buffer with %d entries.",
                        report_cnt,
                        self._data_buffer_size,
                    )
                    report_cnt += 1
                    df = self._convert_buffer_to_dataframe(self._data_buffer)
                    if not df.empty:
                        df[SchedMonitorColumn.WINDOW_START_NS] = window_start_ns
                        df[SchedMonitorColumn.WINDOW_END_NS] = window_end_ns
                        last_timestamp = df[SchedMonitorColumn.WINDOW_END_NS].max()
                        minimum_timestamp = (
                            last_timestamp
                            - self._config.maximum_dataframe_size_in_seconds
                            * TimeConstants.SEC2NANOSEC
                        )
                        df = df[
                            df[SchedMonitorColumn.WINDOW_END_NS] > minimum_timestamp
                        ]
                    self._data_buffer = []
                    self._data_buffer_size = 0
                    self._append_to_disk(df)
                    self._notify_subscribers(df)
                    last_report_time = time.time()
                    window_start_ns = window_end_ns
            except Exception as exc:
                LOGGER.warning("Parse error: %s", exc)
                raise exc

        self._running = False

    @abstractmethod
    def _read_next_message(self, proc: Popen[bytes]) -> bytes:
        """Read the next complete message."""

    @abstractmethod
    def _on_recv_line(self, line: bytes) -> Any:
        """Parse one record from the incoming message."""

    @abstractmethod
    def _convert_buffer_to_dataframe(self, buffer: list) -> pd.DataFrame:
        """Convert buffer records to a DataFrame."""

    def clear_disk_storage(self):
        self._storage.clear_all()

    def _append_to_disk(self, df: pd.DataFrame):
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
        self._subscribers.pop(name, None)
        if not self._subscribers:
            self._stop()

    def _notify_subscribers(self, df: pd.DataFrame):
        for name, callback in self._subscribers.items():
            callback(df)

    def get_full_data(self) -> pd.DataFrame:
        if os.path.exists(self._data_file):
            try:
                return pd.read_csv(
                    self._data_file, header=None, names=SCHED_MONITOR_COLUMNS
                )
            except (OSError, ValueError, IOError) as exc:
                LOGGER.error("Failed to read sched csv data file: %s", exc)
        else:
            LOGGER.error("Data file %s does not exist.", self._data_file)
        return pd.DataFrame(columns=SCHED_MONITOR_COLUMNS)

    def _cleanup(self):
        self._stop(wait=True, timeout=5.0)
        if self._process_lock_fd is not None:
            fcntl.flock(self._process_lock_fd, fcntl.LOCK_UN)
            os.close(self._process_lock_fd)


class SchedMonitorByCSV(SchedMonitor):
    """CSV output sched monitor."""

    def _msg_type_compatible(self, msg_type: str) -> bool:
        return msg_type == CacheSnifferConstants.CACHE_SNIFFER_MSG_CSV

    def _read_next_message(self, proc: subprocess.Popen[bytes]) -> bytes:
        return proc.stdout.readline()

    def _on_recv_line(self, line: bytes) -> Any:
        decoded = line.decode("utf-8").strip()
        if not decoded:
            return None
        if decoded.lower().startswith("pid,tgid,cpu"):
            return None
        return decoded.split(",")

    def _convert_buffer_to_dataframe(self, buffer):
        if len(buffer) == 0:
            return pd.DataFrame(columns=SCHED_MONITOR_RAW_COLUMNS)
        return pd.DataFrame(buffer, columns=SCHED_MONITOR_RAW_COLUMNS)


if EnvManager().msgspec_compatible():
    import msgspec

    class SchedEvent(msgspec.Struct):
        pid: int
        tgid: int
        cpu: int
        time: int

    class SchedMonitorByMsgSpec(SchedMonitor):
        """Msgspec output sched monitor."""

        def __init__(self):
            super().__init__()
            self.msgspec_decoder = msgspec.msgpack.Decoder(SchedEvent)

        def _msg_type_compatible(self, msg_type: str) -> bool:
            return msg_type == CacheSnifferConstants.CACHE_SNIFFER_MSG_MSGSPEC

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
            self, buffer: list[SchedEvent]
        ) -> pd.DataFrame:
            if not buffer:
                return pd.DataFrame(columns=SCHED_MONITOR_RAW_COLUMNS)
            return pd.DataFrame.from_records(buffer, columns=SCHED_MONITOR_RAW_COLUMNS)


def get_sched_monitor() -> SchedMonitor:
    """Get the sched monitor instance."""
    if (
        EnvManager().msgspec_compatible()
        and GlobalConfigManager().get_config().sniffer_config.cpu_sniffer.msg_style
        == CacheSnifferConstants.CACHE_SNIFFER_MSG_MSGSPEC
    ):
        return SchedMonitorByMsgSpec.get_instance()
    return SchedMonitorByCSV.get_instance()


__all__ = ["get_sched_monitor"]
