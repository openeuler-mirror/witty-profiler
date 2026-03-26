"""Socket sniffer abstraction for reading kernel-level socket statistics.

Reads socket communication statistics collected by the socket monitor (eBPF or
similar kernel instrumentation) and exposes query APIs for topology graph
construction. Provides SocketSniffer singleton managing data collection.

Key Components:
    - SocketSniffer: Abstract base class for socket data collection
    - CSVSocketSniffer: CSV file-based implementation (reads monitor output)
    - SocketConnectionInfo: Dataclass for parsed socket connection records
    - get_socket_sniffer(): Factory function returning configured sniffer

Features:
    - Singleton pattern per sniffer type
    - Incremental data reading via get_connections_since(timestamp)
    - Automatic data refresh with configurable interval
    - Thread-safe lock protection for concurrent readers
    - Pandas-based aggregation and filtering

Data Sources:
    CSVSocketSniffer reads from SocketMonitor output (typically
    /tmp/witty_profiler/socket_traffic.csv). Monitor records include:
    - PID/TID, local/remote addresses and ports
    - Function name (send, recv, sendto, recvfrom)
    - Start/end timestamps
    - Byte and packet counts

Usage:
    ```python
    # Get singleton sniffer
    sniffer = get_socket_sniffer()
    sniffer.start()

    # Query connections since timestamp
    connections = sniffer.get_connections_since(start_time)
    for conn in connections:
        print(f"PID {conn.local_pid} → {conn.remote_addr}:{conn.remote_port}")

    sniffer.stop()
    ```

Configuration:
    Sniffer settings loaded from GlobalConfigManager.global_config.sniffer_config.
    Includes file paths, refresh intervals, and filtering options.

Notes:
    Requires SocketMonitor to be running and producing valid CSV output.
    Data refresh controlled by refresh_interval_sec (default: 0.5s).
    Thread-safe for multi-collector environments.
"""

from __future__ import annotations

import threading
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from witty_profiler.common.constants import TimeConstants
from witty_profiler.common.logging import get_logger
from witty_profiler.config_manager.config_manager import GlobalConfigManager
from witty_profiler.config_manager.configs import SocketSnifferConfig
from witty_profiler.edge.socket.socket_monitor import (
    MONITOR_COLUMNS,
    MONITOR_NON_STAT_COLUMNS,
    MonitorColumn,
    get_socket_monitor,
)
from witty_profiler.storage.rotated_file_storage import RotatedFileStorage

LOGGER = get_logger(__name__)


@dataclass(frozen=True)
class SocketConnectionInfo:
    """Socket connection stats from a single sampling window."""

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

    @property
    def connection_type(self) -> str:
        func = (self.function or "").lower()
        if "udp" in func:
            return "UDP"
        if "tcp" in func:
            return "TCP"
        return "UNKNOWN"


class SocketSniffer:
    """Socket sniffer backed by SocketMonitor CSV/MsgSpec output."""

    def __init__(self, dataframe: Optional[pd.DataFrame]):
        super().__init__()
        mngr: GlobalConfigManager = GlobalConfigManager.get_instance()
        self._config: SocketSnifferConfig = (
            mngr.get_config().sniffer_config.socket_sniffer
        )
        self._monitor = get_socket_monitor()
        self._record_lock = threading.RLock()

        self._data_frame: pd.DataFrame = self._preprocess_df(dataframe)

        self._records: list[pd.DataFrame] = []
        self.record_cnt_total: int = 0
        self._subscription_name: str = None

    def start(self) -> bool:
        """Start the sniffer by registering a subscriber to the SocketMonitor."""
        RETRY_COUNT = 3
        if self._subscription_name is not None:
            LOGGER.warning("SocketSniffer already started.")
            return True
        with self._record_lock:
            self._records = []
            self.record_cnt_total = 0
        for _ in range(RETRY_COUNT):
            try:
                self._subscription_name: str = f"socket_sniffer_{uuid.uuid4()}"
                self._monitor.register_subscriber(
                    self._subscription_name, self._record_df
                )
                break
            except ValueError:  # 已经存在同名订阅
                # 重设名字
                LOGGER.warning(f"Retrying subscription {self._subscription_name}...")
                self._subscription_name: str = None
        return self._subscription_name is not None

    def _record_df(self, df: pd.DataFrame):
        # TODO: 是否有必要加锁
        with self._record_lock:
            self._records.append(df)
            self.record_cnt_total += 1

    def stop(self):
        """Stop the subscription to the SocketMonitor and update data."""
        if self._subscription_name is not None:
            self._monitor.unregister_subscriber(self._subscription_name)
        self._subscription_name = None
        self.update_dataframe(drop_previous=False)

    def _preprocess_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """Preprocess the raw dataframe from sniffer output."""
        if df is None or df.empty:
            return pd.DataFrame(columns=MONITOR_COLUMNS)
        columns = df.columns.tolist()
        # 有效性确认
        for col in MONITOR_COLUMNS:
            if col not in columns:
                LOGGER.error(
                    "SocketSniffer: missing required column '%s' in sniffer data", col
                )
                return pd.DataFrame([], columns=MONITOR_COLUMNS)
        df = df[MONITOR_COLUMNS]
        # 类型处理
        for col in [
            MonitorColumn.LOCAL_PID,
            MonitorColumn.LOCAL_TID,
            MonitorColumn.LOCAL_PORT,
            MonitorColumn.REMOTE_PORT,
            MonitorColumn.START_TIME,
            MonitorColumn.END_TIME,
            MonitorColumn.DATA_SIZE_TOTAL,
            MonitorColumn.PACKET_CNT,
        ]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(-1).astype(int)
        # LOGGER.info("Loaded socket sniffer data frame with %d rows:\n%s", len(df), df)
        return df

    def update_dataframe(self, drop_previous=False) -> pd.DataFrame:
        """Update and return the current dataframe with new records."""
        # 优先从自己的_records中获取数据
        # 双缓冲
        if drop_previous:
            LOGGER.debug("Dropping previous records.")
            self._data_frame = self._preprocess_df(None)
        update_records: list[pd.DataFrame] = []
        # 不必加锁
        with self._record_lock:
            update_records = self._records
            self._records: list[pd.DataFrame] = []

        # 无更新
        if not update_records:
            return self._data_frame

        # 合并更新
        update_df: pd.DataFrame = self._preprocess_df(
            pd.concat(update_records, ignore_index=True)
        )
        # 合并历史数据
        self._data_frame: pd.DataFrame = pd.concat(
            [
                self._data_frame,
                update_df,
            ]
        )
        last_timestamp = update_df[MonitorColumn.END_TIME].max()
        minimum_timestamp = (
            last_timestamp
            - self._config.maximum_dataframe_size_in_seconds * TimeConstants.SEC2NANOSEC
        )
        self._data_frame = self._data_frame[
            self._data_frame[MonitorColumn.END_TIME] > minimum_timestamp
        ]
        return self._data_frame

    def query_all_connections(self) -> list[SocketConnectionInfo]:
        df = self.update_dataframe()
        return [SocketConnectionInfo(**row.to_dict()) for _, row in df.iterrows()]

    def query_all_recv_sockets(self) -> list[tuple[str, int]]:
        """Return all sockets with recv activity recorded."""
        df = self.update_dataframe()
        recv_df = df[
            df[MonitorColumn.FUNCTION].str.contains("recv", case=False, na=False)
        ]
        send_df = df[
            df[MonitorColumn.FUNCTION].str.contains("send", case=False, na=False)
        ]

        recv_socket_df = recv_df[
            [MonitorColumn.LOCAL_ADDR, MonitorColumn.LOCAL_PORT]
        ].drop_duplicates()
        send_socket_df = send_df[
            [MonitorColumn.REMOTE_ADDR, MonitorColumn.REMOTE_PORT]
        ].drop_duplicates()

        return [
            (row[MonitorColumn.LOCAL_ADDR], row[MonitorColumn.LOCAL_PORT])
            for _, row in recv_socket_df.iterrows()
        ] + [
            (row[MonitorColumn.REMOTE_ADDR], row[MonitorColumn.REMOTE_PORT])
            for _, row in send_socket_df.iterrows()
        ]

    def query_all_pids(self) -> list[int]:
        """Return all PIDs with socket activity recorded."""
        df = self.update_dataframe()
        pid_df = df[MonitorColumn.LOCAL_PID].drop_duplicates()
        return pid_df.tolist()

    def query_recv_at_pid(self, pid: int) -> list[SocketConnectionInfo]:
        """Return all socket send connections to a given PID."""

        df = self.update_dataframe()
        recv_df = df[
            (df[MonitorColumn.FUNCTION].str.contains("recv", case=False, na=False))
            & (df[MonitorColumn.LOCAL_PID] == pid)
        ]

        recv_df = recv_df.groupby(
            MONITOR_NON_STAT_COLUMNS,
            as_index=False,
        ).agg(
            {
                MonitorColumn.START_TIME: "min",
                MonitorColumn.END_TIME: "max",
                MonitorColumn.DATA_SIZE_TOTAL: "sum",
                MonitorColumn.PACKET_CNT: "sum",
            }
        )

        connections = []
        for _, row in recv_df.iterrows():
            connections.append(SocketConnectionInfo(**row.to_dict()))

        return connections

    def query_send_at_pid(self, pid: int) -> list[SocketConnectionInfo]:
        """Return all socket send connections to a given PID."""

        df = self.update_dataframe()
        send_df = df[
            (df[MonitorColumn.FUNCTION].str.contains("send", case=False, na=False))
            & (df[MonitorColumn.LOCAL_PID] == pid)
        ]
        send_df = send_df.groupby(
            MONITOR_NON_STAT_COLUMNS,
            as_index=False,
        ).agg(
            {
                MonitorColumn.START_TIME: "min",
                MonitorColumn.END_TIME: "max",
                MonitorColumn.DATA_SIZE_TOTAL: "sum",
                MonitorColumn.PACKET_CNT: "sum",
            }
        )
        # # LOGGER.debug("send at PID:%s :\n%s", pid, send_df)
        connections = []
        for _, row in send_df.iterrows():
            connections.append(SocketConnectionInfo(**row.to_dict()))
        return connections

    def query_recv_at_socket(
        self, socket_addr: str, socket_port: int
    ) -> list[SocketConnectionInfo]:
        """Return all socket recv connections at a given socket."""

        df = self.update_dataframe()

        recv_df = df[
            (df[MonitorColumn.FUNCTION].str.contains("recv", case=False, na=False))
            & (df[MonitorColumn.LOCAL_ADDR] == socket_addr)
            & (df[MonitorColumn.LOCAL_PORT] == socket_port)
        ]
        recv_df = recv_df.groupby(
            MONITOR_NON_STAT_COLUMNS,
            as_index=False,
        ).agg(
            {
                MonitorColumn.START_TIME: "min",
                MonitorColumn.END_TIME: "max",
                MonitorColumn.DATA_SIZE_TOTAL: "sum",
                MonitorColumn.PACKET_CNT: "sum",
            }
        )
        connections = []
        for _, row in recv_df.iterrows():
            connections.append(SocketConnectionInfo(**row.to_dict()))
        # LOGGER.debug(
        #    "recv connection at %s:%s :\n%s", socket_addr, socket_port, recv_df
        # )
        return connections

    def query_send_to_socket(
        self, socket_addr: str, socket_port: int
    ) -> list[SocketConnectionInfo]:
        """Return all socket send connections to a given socket."""

        df = self.update_dataframe()
        send_df = df[
            (df[MonitorColumn.FUNCTION].str.contains("send", case=False, na=False))
            & (df[MonitorColumn.REMOTE_ADDR] == socket_addr)
            & (df[MonitorColumn.REMOTE_PORT] == socket_port)
        ]
        send_df = send_df.groupby(
            MONITOR_NON_STAT_COLUMNS,
            as_index=False,
        ).agg(
            {
                MonitorColumn.START_TIME: "min",
                MonitorColumn.END_TIME: "max",
                MonitorColumn.DATA_SIZE_TOTAL: "sum",
                MonitorColumn.PACKET_CNT: "sum",
            }
        )
        connections = []
        for _, row in send_df.iterrows():
            connections.append(SocketConnectionInfo(**row.to_dict()))
        # LOGGER.debug(
        #    "send connection to %s:%s :\n%s", socket_addr, socket_port, send_df
        # )
        return connections


def get_socket_sniffer(dataframe: Optional[pd.DataFrame] = None) -> SocketSniffer:
    """Get the default socket sniffer instance."""
    return SocketSniffer(dataframe=dataframe)


__all__ = ["SocketSniffer", "SocketConnectionInfo", "get_socket_sniffer"]


if __name__ == "__main__":
    sniffer = SocketSniffer()
    LOGGER.info("\n%s", sniffer.query_all_pids())
    LOGGER.info("\n%s", sniffer.query_recv_at_pid(4125))
    LOGGER.info("\n%s", sniffer.query_send_at_pid(4125))
    LOGGER.info("\n%s", sniffer.query_recv_at_socket("127.0.0.1", 49401))
    LOGGER.info("\n%s", sniffer.query_send_to_socket("127.0.0.1", 49401))
