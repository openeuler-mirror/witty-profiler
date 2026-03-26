"""Provide RDMA statistics by periodic snapshots and diffs.

Collects per-port counters from RDMA tooling or sysfs, computes deltas
between snapshots, and exposes per-second statistics for consumers.

Notes:
    - Requires Linux RDMA tooling (rdma-core) or sysfs counters.
    - Counter coverage depends on available provider output.
"""

import json
import os
import re
import subprocess
import time
from dataclasses import asdict, dataclass, field
from threading import Event, RLock, Thread
from typing import Optional, Tuple

from witty_profiler.common.logging import get_logger
from witty_profiler.config_manager.config_manager import GlobalConfigManager

LOGGER = get_logger(__name__)

SYSFS_INFINIBAND_PATH = "/sys/class/infiniband"


@dataclass
class PDRecord:
    dev: str = ""
    pdn: int = -1
    local_dma_lkey: int = -1
    ctxn: int = -1
    pid: Optional[int] = None

    def valid(self) -> bool:
        return (
            self.dev != "" and self.pdn >= 0 and self.pid is not None and self.pid > 0
        )


@dataclass
class QPRecord:
    device: str
    port: int
    lqpn: int
    rqpn: int
    state: str
    pdn: int
    pid: Optional[int] = None


@dataclass
class MRRecord:
    device: str
    mrn: int
    lkey: int
    rkey: int
    mrlen: int
    pdn: int
    pid: Optional[int] = None


@dataclass
class RDMAStatistic:
    dev: str = ""
    port: int = 0
    send_pkts: float = 0
    recv_pkts: float = 0
    dupl_pkts: float = 0
    rdma_sends: float = 0
    rdma_recvs: float = 0

    def empty(self) -> bool:
        return (
            self.send_pkts == 0
            and self.recv_pkts == 0
            and self.dupl_pkts == 0
            and self.rdma_sends == 0
            and self.rdma_recvs == 0
        )

    def __itruediv__(self, interval: float) -> "RDMAStatistic":
        if interval <= 0:
            interval = 1e-9
        self.send_pkts /= interval
        self.recv_pkts /= interval
        self.dupl_pkts /= interval
        self.rdma_sends /= interval
        self.rdma_recvs /= interval
        return self

    def __sub__(self, other: "RDMAStatistic") -> "RDMAStatistic":
        return RDMAStatistic(
            dev=self.dev,
            port=self.port,
            send_pkts=self.send_pkts - other.send_pkts,
            recv_pkts=self.recv_pkts - other.recv_pkts,
            dupl_pkts=self.dupl_pkts - other.dupl_pkts,
            rdma_sends=self.rdma_sends - other.rdma_sends,
            rdma_recvs=self.rdma_recvs - other.rdma_recvs,
        )

    def copy(self) -> "RDMAStatistic":
        return RDMAStatistic(
            dev=self.dev,
            port=self.port,
            send_pkts=self.send_pkts,
            recv_pkts=self.recv_pkts,
            dupl_pkts=self.dupl_pkts,
            rdma_sends=self.rdma_sends,
            rdma_recvs=self.rdma_recvs,
        )


@dataclass
class RDMAStatisticSnapshot:
    timestamp: float = field(default_factory=time.time)
    key2stat: dict[Tuple[str, int], RDMAStatistic] = field(default_factory=dict)

    def diff(self, other: "RDMAStatisticSnapshot") -> "RDMAStatisticPerSecond":
        interval = self.timestamp - other.timestamp
        if interval <= 0:
            interval = 1e-9
        result: dict[Tuple[str, int], RDMAStatistic] = {}

        for key in self.key2stat:
            if key in other.key2stat:
                stat = self.key2stat[key] - other.key2stat[key]
            else:
                stat = self.key2stat[key].copy()
            if stat.empty():
                continue
            stat /= interval
            result[key] = stat

        return RDMAStatisticPerSecond(key2stat=result)


@dataclass
class RDMAStatisticPerSecond:
    key2stat: dict[Tuple[str, int], RDMAStatistic]


class RDMASnapshotCollector:
    """Collects RDMA statistics from rdma CLI or sysfs."""

    COUNTER_FIELD_MAP = {
        "send_pkts": {
            "sent_pkts",
            "send_pkts",
            "tx_pkts",
            "out_pkts",
            "port_xmit_packets",
            "xmit_packets",
        },
        "recv_pkts": {
            "rcvd_pkts",
            "recv_pkts",
            "rx_pkts",
            "in_pkts",
            "port_rcv_packets",
            "rcv_packets",
        },
        "dupl_pkts": {"dupl_pkts", "dup_pkts", "duplicate_pkts", "duplicate_request"},
        "rdma_sends": {
            "rdma_sends",
            "rdma_send",
            "rdma_send_pkts",
            "rdma_send_packets",
        },
        "rdma_recvs": {
            "rdma_recvs",
            "rdma_recv",
            "rdma_recv_pkts",
            "rdma_recv_packets",
        },
    }

    def collect(self) -> RDMAStatisticSnapshot:
        stats = self._from_rdma_json()
        if not stats:
            stats = self._from_rdma_text()
        if not stats:
            stats = self._from_sysfs()
        return RDMAStatisticSnapshot(timestamp=time.time(), key2stat=stats)

    def _run_rdma(self, args: list[str]) -> Optional[str]:
        try:
            result = subprocess.run(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            return None
        if result.returncode != 0:
            LOGGER.debug("rdma command failed (%s): %s", " ".join(args), result.stderr)
            return None
        return result.stdout

    def _safe_int(self, value: object) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        text = str(value).strip()
        if not text:
            return None
        try:
            return int(text, 16) if text.lower().startswith("0x") else int(text)
        except ValueError:
            return None

    def _parse_counter_value(self, value: object) -> Optional[int]:
        if isinstance(value, dict):
            for key in ("value", "val", "v"):
                if key in value:
                    return self._safe_int(value[key])
            return 0
        return self._safe_int(value)

    def _build_stat(self, dev: str, port: int, counters: dict) -> RDMAStatistic:
        lower_counters = {str(k).lower(): v for k, v in counters.items()}
        values: dict[str, float] = {}
        for field_name, aliases in self.COUNTER_FIELD_MAP.items():
            val = 0
            for alias in aliases:
                if alias in lower_counters:
                    parsed_val = self._parse_counter_value(lower_counters[alias])
                    if parsed_val is not None:
                        val = parsed_val
                    break
            values[field_name] = val
        return RDMAStatistic(dev=dev, port=port, **values)

    def _from_rdma_json(self) -> dict[Tuple[str, int], RDMAStatistic]:
        output = self._run_rdma(["rdma", "statistic", "-j"])
        if not output:
            return {}
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            return {}

        items = self._extract_items(data)
        stats: dict[Tuple[str, int], RDMAStatistic] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            dev = (
                item.get("ifname")
                or item.get("dev")
                or item.get("device")
                or item.get("name")
            )
            port = self._safe_int(item.get("port"))
            counters = (
                item.get("counter") or item.get("counters") or item.get("stats") or item
            )
            if isinstance(counters, list):
                counters = {
                    str(e.get("name") or e.get("key")): e.get("value")
                    for e in counters
                    if isinstance(e, dict) and (e.get("name") or e.get("key"))
                }
            if dev is None or port <= 0:
                continue
            stat = self._build_stat(dev, port, counters)
            stats[(stat.dev, stat.port)] = stat
        return stats

    def _extract_items(self, data: object) -> list:
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("statistic", "statistics", "data", "items"):
                if key in data and isinstance(data[key], list):
                    return data[key]
            return [data]
        return []

    def _from_rdma_text(self) -> dict[Tuple[str, int], RDMAStatistic]:
        output = self._run_rdma(["rdma", "statistic"])
        if not output:
            return {}
        stats: dict[Tuple[str, int], RDMAStatistic] = {}
        all_aliases = set()
        for aliases in self.COUNTER_FIELD_MAP.values():
            all_aliases.update(aliases)

        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            tokens = re.split(r"\s+", line)
            dev, port = self._extract_dev_port(tokens)
            pairs = self._parse_kv(tokens)
            if dev is None:
                dev = pairs.get("dev") or pairs.get("device") or pairs.get("ifname")
            if port == 0:
                port = self._safe_int(pairs.get("port"))
            if dev is None or port <= 0:
                continue
            counters = {k: v for k, v in pairs.items() if k in all_aliases}
            stat = self._build_stat(dev, port, counters)
            stats[(stat.dev, stat.port)] = stat
        return stats

    def _extract_dev_port(self, tokens: list[str]) -> Tuple[Optional[str], int]:
        for token in tokens:
            candidate = token.strip().strip(":,")
            if "/" in candidate:
                parts = candidate.split("/", 1)
                if parts[1].isdigit():
                    return parts[0], int(parts[1])
        return None, 0

    def _parse_kv(self, tokens: list[str]) -> dict[str, str]:
        pairs: dict[str, str] = {}
        for token in tokens:
            token = token.strip().strip(",")
            if ":" in token:
                key, value = token.split(":", 1)
                if key and value:
                    pairs[key.lower()] = value
        return pairs

    def _from_sysfs(self) -> dict[Tuple[str, int], RDMAStatistic]:
        if not os.path.isdir(SYSFS_INFINIBAND_PATH):
            return {}
        stats: dict[Tuple[str, int], RDMAStatistic] = {}
        for dev in os.listdir(SYSFS_INFINIBAND_PATH):
            ports_path = os.path.join(SYSFS_INFINIBAND_PATH, dev, "ports")
            if not os.path.isdir(ports_path):
                continue
            for port_name in os.listdir(ports_path):
                counters_dir = os.path.join(ports_path, port_name, "counters")
                if not os.path.isdir(counters_dir):
                    continue
                port = self._safe_int(port_name)
                stat = RDMAStatistic(
                    dev=dev,
                    port=port,
                    send_pkts=self._read_sysfs_counter(
                        counters_dir, "port_xmit_packets"
                    ),
                    recv_pkts=self._read_sysfs_counter(
                        counters_dir, "port_rcv_packets"
                    ),
                    dupl_pkts=self._read_sysfs_counter(
                        counters_dir, "port_rcv_dup_packets"
                    ),
                    rdma_sends=0,
                    rdma_recvs=0,
                )
                stats[(stat.dev, stat.port)] = stat
        return stats

    def _read_sysfs_counter(self, counters_dir: str, name: str) -> int:
        try:
            with open(os.path.join(counters_dir, name), "r", encoding="utf-8") as f:
                return self._safe_int(f.read().strip())
        except OSError:
            return 0


class RDMAResourceCollector:
    """Collects RDMA QP and MR records from rdma CLI."""

    def _run_rdma(self, args: list[str]) -> Optional[str]:
        try:
            result = subprocess.run(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            return None
        if result.returncode != 0:
            return None
        return result.stdout

    def _safe_int(self, value: object) -> int:
        if value is None:
            return 0
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        text = str(value).strip()
        if not text:
            return 0
        try:
            return int(text, 16) if text.lower().startswith("0x") else int(text)
        except ValueError:
            return 0

    def _flatten_json(self, data: object) -> list[dict]:
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            for key in ("qp", "mr", "res", "data", "items"):
                if key in data:
                    return self._flatten_json(data[key])
            return [data]
        return []

    def _parse_text_records(self, output: str) -> list[dict]:
        records = []
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            tokens = re.split(r"\s+", line)
            pairs: dict[str, str] = {}
            for token in tokens:
                token = token.strip().strip(",")
                if ":" in token:
                    key, value = token.split(":", 1)
                    if key and value:
                        pairs[key.lower()] = value
            records.append(pairs)
        return records

    def get_qp_records(self) -> list[QPRecord]:
        output = self._run_rdma(["rdma", "res", "show", "qp", "-j"])
        records: list[dict] = []
        if output:
            try:
                records = self._flatten_json(json.loads(output))
            except json.JSONDecodeError:
                pass
        if not records:
            output = self._run_rdma(["rdma", "res", "show", "qp"])
            if output:
                records = self._parse_text_records(output)

        parsed: list[QPRecord] = []
        for item in records:
            device = item.get("dev") or item.get("device") or item.get("ifname")
            lqpn = self._safe_int(item.get("lqpn") or item.get("qpn"))
            if device is None or lqpn is None or lqpn == 0:
                continue
            parsed.append(
                QPRecord(
                    device=device,
                    port=self._safe_int(item.get("port")),
                    lqpn=lqpn,
                    rqpn=self._safe_int(item.get("rqpn")),
                    state=str(item.get("state") or ""),
                    pdn=self._safe_int(item.get("pdn")),
                    pid=self._safe_int(item.get("pid")),
                )
            )
        return parsed

    def get_mr_records(self) -> list[MRRecord]:
        output = self._run_rdma(["rdma", "res", "show", "mr", "-j"])
        records: list[dict] = []
        if output:
            try:
                records = self._flatten_json(json.loads(output))
            except json.JSONDecodeError:
                pass
        if not records:
            output = self._run_rdma(["rdma", "res", "show", "mr"])
            if output:
                records = self._parse_text_records(output)

        parsed: list[MRRecord] = []
        for item in records:
            device = item.get("dev") or item.get("device") or item.get("ifname")
            mrn = self._safe_int(item.get("mrn") or item.get("mr"))
            if device is None or mrn is None or mrn == 0:
                continue
            parsed.append(
                MRRecord(
                    device=device,
                    mrn=mrn,
                    lkey=self._safe_int(item.get("lkey")),
                    rkey=self._safe_int(item.get("rkey")),
                    mrlen=self._safe_int(
                        item.get("mrlen") or item.get("len") or item.get("length")
                    ),
                    pdn=self._safe_int(item.get("pdn")),
                    pid=self._safe_int(item.get("pid")),
                )
            )
        return parsed

    def get_pd_records(self) -> list[PDRecord]:
        output = self._run_rdma(["rdma", "res", "show", "pd", "-j"])
        records: list[dict] = []
        if output:
            try:
                records: list[dict] = self._flatten_json(json.loads(output))
            except json.JSONDecodeError:
                pass
        if not records:
            output = self._run_rdma(["rdma", "res", "show", "pd"])
            if output:
                records: list[dict] = self._parse_text_records(output)

        parsed: list[PDRecord] = []
        for item in records:
            device = item.get("dev") or item.get("device") or item.get("ifname")
            pdn = self._safe_int(item.get("pdn"))
            if device is None:
                continue
            parsed.append(
                PDRecord(
                    dev=device,
                    pdn=pdn,
                    local_dma_lkey=self._safe_int(item.get("local_dma_lkey")),
                    ctxn=self._safe_int(item.get("ctxn")),
                    pid=self._safe_int(item.get("pid")),
                )
            )
        return parsed


class RDMAMonitor:
    def __init__(self):
        self.config = GlobalConfigManager().get_config().sniffer_config.rdma_sniffer
        self._update_interval = self.config.update_interval_by_second
        self._snapshot_collector = RDMASnapshotCollector()
        self._resource_collector = RDMAResourceCollector()
        self._last_snapshot: RDMAStatisticSnapshot = self._snapshot_collector.collect()
        LOGGER.debug(
            "Initial RDMA snapshot collected at %f (entrys: %s)",
            self._last_snapshot.timestamp,
            self._last_snapshot.key2stat.keys(),
        )
        self._stats_per_second: Optional[RDMAStatisticPerSecond] = None
        self._thread: Optional[Thread] = None
        self._stop_event: Optional[Event] = None
        self._lock = RLock()

    def start(self):
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                LOGGER.warning("RDMA monitoring is already running.")
                return
            self._stop_event = Event()
            self._thread = Thread(target=self._loop, daemon=True)
            self._thread.start()

    def _loop(self):
        stop_event = self._stop_event
        if stop_event is None:
            return
        while not stop_event.is_set():
            with self._lock:
                self._update()
            if stop_event.wait(self._update_interval):
                break

    def stop(self, timeout: float = 0.1):
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                LOGGER.warning("RDMA monitoring is not running.")
                return
            if self._stop_event is None:
                return
            self._stop_event.set()
        self._thread.join(timeout=timeout)
        with self._lock:
            self._thread = None
            self._stop_event = None

    def clear(self):
        with self._lock:
            self._update()
            self._stats_per_second = None

    def _update(self):
        new_snapshot = self._snapshot_collector.collect()
        self._stats_per_second = new_snapshot.diff(self._last_snapshot)
        self._last_snapshot = new_snapshot

    def get_statistics_per_second(self) -> RDMAStatisticPerSecond:
        with self._lock:
            if self._stats_per_second is None:
                self._update()
            return self._stats_per_second or RDMAStatisticPerSecond(key2stat={})

    def get_rdma_link_stats(self, dev: str, port: int) -> Optional[RDMAStatistic]:
        with self._lock:
            return self._last_snapshot.key2stat.get((dev, port))

    def get_rdma_qp_records(self) -> list[QPRecord]:
        return self._resource_collector.get_qp_records()

    def get_rdma_mr_records(self) -> list[MRRecord]:
        return self._resource_collector.get_mr_records()

    def get_rdma_pd_records(self) -> list[PDRecord]:
        return self._resource_collector.get_pd_records()


__all__ = ["RDMAMonitor"]


if __name__ == "__main__":
    monitor = RDMAMonitor()
    monitor.start()
    time.sleep(5)
    stats = monitor.get_statistics_per_second()
    for (dev, port), stat in stats.key2stat.items():
        print(
            f"Device: {dev}, Port: {port}, "
            f"Send pkts/s: {stat.send_pkts}, Recv pkts/s: {stat.recv_pkts}, "
            f"Dupl pkts/s: {stat.dupl_pkts}, RDMA Sends/s: {stat.rdma_sends}, "
            f"RDMA Recvs/s: {stat.rdma_recvs}"
        )
    print(json.dumps([asdict(qp) for qp in monitor.get_rdma_qp_records()], indent=2))
    monitor.stop()
