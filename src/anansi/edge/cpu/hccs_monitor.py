"""HCCS PMU monitor for collecting bandwidth data from eBPF binary.

Manages the pmu_monitor subprocess, parses CSV/msgspec output, and provides
subscription-based data distribution.

Architecture:
    eBPF Binary (pmu_monitor)
        │
        ▼ CSV/MsgSpec output
    HCCSMonitor (this module)
        │
        │ CountersDict subscription
        ▼
    HCCSSniffer

Thread Safety:
    All lifecycle methods protected by RLock.
    Uses Event for graceful shutdown coordination.
    Uses select() for interruptible I/O.

Usage:
    ```python
    monitor = get_hccs_monitor()
    monitor.start()

    # Query current counters
    counters = monitor.get_counters()

    # Or subscribe to updates
    monitor.register_subscriber("my_subscriber", my_callback)

    monitor.stop()
    ```
"""

import atexit
import os
import re
import select
import subprocess
import threading
from typing import Callable, Optional

from anansi.common.constants import HCCSEventType, HCCSMonitorConstants
from anansi.common.env_manager import EnvManager
from anansi.common.logging import get_logger
from anansi.config_manager.config_manager import GlobalConfigManager

LOGGER = get_logger(__name__)

CounterKey = tuple[int, int, int]
CounterValue = tuple[int, float]
CountersDict = dict[CounterKey, CounterValue]

EVENT_DDR = HCCSEventType.EVENT_DDR
EVENT_HHA = HCCSEventType.EVENT_HHA
EVENT_L3C = HCCSEventType.EVENT_L3C
EVENT_PA = HCCSEventType.EVENT_PA

OUTPUT_STYLE_CSV = HCCSMonitorConstants.OUTPUT_STYLE_CSV
OUTPUT_STYLE_MSGSPEC = HCCSMonitorConstants.OUTPUT_STYLE_MSGSPEC


def sniffer_binary_version(binary_path: str) -> list[str]:
    """Get version info from pmu_monitor binary."""
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
        LOGGER.error("Failed to get PMU monitor binary version: %s", e)
    return results


def check_binary_compatible(binary_path: str, expected_style: str) -> bool:
    """Check if binary output style matches expected."""
    LOGGER.debug("Checking PMU monitor binary (%s) compatibility", binary_path)
    try:
        results = sniffer_binary_version(binary_path)
        if not results:
            raise RuntimeError("No output from PMU monitor binary -v")

        LOGGER.debug("PMU monitor binary -v output:\n%s", results)

        pattern = re.compile(r"^output_style:(\w+)\s*\((\d+)\)$")
        for line in results:
            match = pattern.match(line)
            if match:
                style = match.group(1)
                compatible = style == expected_style
                LOGGER.debug(
                    "Output style: %s (expected: %s) -> %s",
                    style,
                    expected_style,
                    "compatible" if compatible else "incompatible",
                )
                return compatible

        LOGGER.warning("Could not find output_style in binary version output")
        return False

    except RuntimeError as e:
        LOGGER.error("Failed to verify PMU monitor binary: %s", e)
        return False


class HCCSMonitor:
    """Singleton monitor for HCCS PMU data collection.

    Thread-safe lifecycle management with graceful shutdown support.
    """

    _instance: Optional["HCCSMonitor"] = None
    _singleton_lock = threading.Lock()

    def __new__(cls) -> "HCCSMonitor":
        if cls._instance is None:
            with cls._singleton_lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._init()
                    cls._instance = instance
        return cls._instance

    def _init(self):
        """Initialize monitor state."""
        self._state_lock = threading.RLock()
        self._stop_event = threading.Event()

        self._running = False
        self._proc: Optional[subprocess.Popen] = None
        self._reader_thread: Optional[threading.Thread] = None

        self._counters: CountersDict = {}
        self._counters_lock = threading.RLock()

        self._subscribers: dict[str, Callable[[CountersDict], None]] = {}
        self._interval_sec: float = 1.0

        mngr = GlobalConfigManager.get_instance()
        self._config = mngr.get_config().collector_config.hccs_collector_config
        self._sniffer_config = mngr.get_config().sniffer_config.hccs_sniffer
        self._binary_path = self._sniffer_config.pmu_monitor_binary_path

        atexit.register(self._cleanup)

    @classmethod
    def get_instance(cls) -> "HCCSMonitor":
        """Get the singleton monitor instance."""
        return cls()

    @property
    def is_running(self) -> bool:
        """Check if the monitor is currently running."""
        with self._state_lock:
            return self._running

    @property
    def binary_path(self) -> str:
        """Get the path to the PMU monitor binary."""
        return self._binary_path

    def _should_enable_hccs(self) -> bool:
        """Check if HCCS monitoring should be enabled."""
        cpu_type = self._config.cpu_type
        if not cpu_type or cpu_type.lower() == "disabled":
            return False

        if cpu_type == "auto_detect":
            env_mgr = EnvManager()
            is_kunpeng = env_mgr.is_kunpeng_920()
            if is_kunpeng:
                cpu_info = env_mgr.get_cpu_info()
                LOGGER.info(
                    "HCCSMonitor: auto-detected Kunpeng 920 CPU (vendor=%s, model=%s)",
                    cpu_info.get("vendor", "unknown"),
                    cpu_info.get("model", "unknown"),
                )
            else:
                LOGGER.info(
                    "HCCSMonitor: auto-detection found non-Kunpeng CPU, disabling"
                )
            return is_kunpeng

        if cpu_type.startswith("920"):
            LOGGER.info(
                "HCCSMonitor: manual CPU type %s assumed to be Kunpeng 920 variant",
                cpu_type,
            )
            return True

        LOGGER.info(
            "HCCSMonitor: manual CPU type %s, proceeding with HCCS monitoring",
            cpu_type,
        )
        return True

    def start(self) -> bool:
        """Start the monitor (thread-safe)."""
        with self._state_lock:
            if self._running:
                LOGGER.warning("HCCSMonitor already running")
                return True

            if not self._should_enable_hccs():
                LOGGER.info(
                    "HCCSMonitor disabled: CPU type mismatch or manual configuration"
                )
                return False

            if not os.path.isfile(self._binary_path):
                LOGGER.warning(
                    "PMU monitor binary not found at %s — HCCSMonitor disabled",
                    self._binary_path,
                )
                return False

            if not check_binary_compatible(self._binary_path, OUTPUT_STYLE_CSV):
                LOGGER.error(
                    "PMU monitor binary not compatible with %s output style",
                    OUTPUT_STYLE_CSV,
                )
                return False

            self._interval_sec = self._config.interval_ms / 1000.0
            cmd = [self._binary_path, "-i", str(self._interval_sec)]

            if self._config.target_sccls:
                cmd.extend(["-t", self._config.target_sccls])

            LOGGER.info("Starting PMU monitor: %s", " ".join(cmd))

            try:
                self._proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    bufsize=0,
                    text=False,
                )
            except Exception as e:
                LOGGER.error("Failed to start PMU monitor: %s", e)
                return False

            self._stop_event.clear()
            self._running = True
            self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._reader_thread.start()

            LOGGER.info("HCCSMonitor started successfully")
            return True

    def stop(self):
        """Stop the monitor (thread-safe)."""
        with self._state_lock:
            if not self._running and self._proc is None:
                return

            LOGGER.info("Stopping HCCSMonitor...")
            self._stop_event.set()
            self._running = False

            if self._proc is not None:
                try:
                    self._proc.terminate()
                    self._proc.wait(timeout=5.0)
                except Exception as e:
                    LOGGER.warning("Failed to stop PMU monitor process: %s", e)
                self._proc = None

            if self._reader_thread is not None:
                self._reader_thread.join(timeout=5.0)
                self._reader_thread = None

        LOGGER.info("HCCSMonitor stopped")

    def clear(self):
        """Clear all cached counter data."""
        with self._counters_lock:
            self._counters.clear()

    def get_counters(self) -> CountersDict:
        """Get a snapshot of current counter values."""
        with self._counters_lock:
            return {k: (v[0], v[1]) for k, v in self._counters.items()}

    @property
    def sccl_ids(self) -> list[int]:
        """Get list of SCCL IDs with available counter data."""
        with self._counters_lock:
            return sorted(set(key[0] for key in self._counters.keys()))

    def register_subscriber(
        self,
        name: str,
        callback: Callable[[CountersDict], None],
        enable_override: bool = False,
    ):
        """Register a subscriber to receive counter updates."""
        with self._state_lock:
            if name in self._subscribers:
                if not enable_override:
                    raise ValueError(f"Subscriber '{name}' already exists")
                LOGGER.warning("Subscriber '%s' already exists, overwriting", name)

            self._subscribers[name] = callback
            LOGGER.info("Registered subscriber '%s'", name)

            if not self._running:
                self._start_internal()

    def unregister_subscriber(self, name: str):
        """Unregister a subscriber."""
        with self._state_lock:
            if name in self._subscribers:
                del self._subscribers[name]
                LOGGER.info("Unregistered subscriber '%s'", name)

            if not self._subscribers:
                self._stop_internal()

    def _start_internal(self):
        """Internal start without lock (caller must hold lock)."""
        self.start()

    def _stop_internal(self):
        """Internal stop without lock (caller must hold lock)."""
        self.stop()

    def _read_loop(self):
        """Read loop with select for interruptible I/O."""
        while not self._stop_event.is_set():
            if self._proc is None or self._proc.poll() is not None:
                break

            try:
                readable, _, _ = select.select([self._proc.stdout], [], [], timeout=0.1)
            except (ValueError, OSError):
                break

            if self._stop_event.is_set():
                break

            if not readable:
                continue

            line = self._proc.stdout.readline()
            if not line:
                break

            self._process_line(line)

        with self._state_lock:
            self._running = False

    def _process_line(self, line: bytes):
        """Parse and process a line of output."""
        try:
            decoded = line.decode("utf-8", errors="replace").strip()
            if not decoded or decoded.startswith("sccl_id"):
                return

            parts = decoded.split(",")
            if len(parts) < 5:
                return

            sccl_id = int(parts[0])
            event_type = int(parts[1])
            event_code = int(parts[2])
            count = int(parts[3])
            interval_sec = float(parts[4])

            with self._counters_lock:
                self._counters[(sccl_id, event_type, event_code)] = (
                    count,
                    interval_sec,
                )

            self._notify_subscribers()

        except (ValueError, IndexError) as e:
            LOGGER.debug("PMU CSV parse error: %s (line: %s)", e, decoded[:50])

    def _notify_subscribers(self):
        """Notify all subscribers with current counter data."""
        counters = self.get_counters()
        for name, callback in list(self._subscribers.items()):
            try:
                callback(counters)
            except Exception as e:
                LOGGER.warning("Subscriber '%s' callback error: %s", name, e)

    def _cleanup(self):
        """Cleanup resources on process exit."""
        self.stop()


def get_hccs_monitor() -> HCCSMonitor:
    """Get the singleton HCCSMonitor instance."""
    return HCCSMonitor.get_instance()


__all__ = [
    "HCCSMonitor",
    "get_hccs_monitor",
    "CounterKey",
    "CounterValue",
    "CountersDict",
    "OUTPUT_STYLE_CSV",
    "OUTPUT_STYLE_MSGSPEC",
    "EVENT_DDR",
    "EVENT_HHA",
    "EVENT_L3C",
    "EVENT_PA",
]
