"""Provide a lightweight cache sniffer wrapper over CacheMonitor output.

Standardizes cache miss dataframe columns and exposes a minimal API for
consuming buffered cache miss records via CacheMonitor.

Notes:
    - Columns align with cache miss binary output: cpu/tgid/pid/total/l1i/llc.
    - Collection is delegated to CacheMonitor; this wrapper focuses on
      dataframe normalization and buffering.


"""

import threading
import time
import uuid
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from witty_profiler.common.constants import CacheMonitorColumn, TimeConstants
from witty_profiler.common.logging import get_logger
from witty_profiler.config_manager.config_manager import GlobalConfigManager
from witty_profiler.config_manager.configs import CPUSnifferConfig
from witty_profiler.edge.cpu.cache_monitor import CacheMonitor, get_cache_monitor
from witty_profiler.edge.cpu.numa_deployment import StaticNumaDeployment
from witty_profiler.edge.cpu.numa_edge import CacheMissStats

LOGGER = get_logger(__name__)


@dataclass(frozen=True)
class CacheMissInfo:
    numa_id: int
    total: int
    l1i: int
    llc: int


class CacheSniffer:
    """Cache sniffer backed by CacheMonitor output."""

    def __init__(self, dataframe: Optional[pd.DataFrame] = None):
        mngr: GlobalConfigManager = GlobalConfigManager.get_instance()
        self._config: CPUSnifferConfig = mngr.get_config().sniffer_config.cpu_sniffer
        self._cache_df: pd.DataFrame = self._preprocess_df(dataframe)
        self._monitor: CacheMonitor = get_cache_monitor()
        self._subscription_name: Optional[str] = None
        self._records: list[pd.DataFrame] = []
        self._record_lock = threading.RLock()

    def _preprocess_df(self, dataframe: Optional[pd.DataFrame]) -> pd.DataFrame:
        if dataframe is None or dataframe.empty:
            return pd.DataFrame(columns=CacheMonitorColumn.columns())
        columns = dataframe.columns.tolist()
        for col in CacheMonitorColumn.columns():
            if col not in columns:
                LOGGER.error(
                    "CacheSniffer: missing required column '%s' in sniffer data", col
                )
                return pd.DataFrame(columns=CacheMonitorColumn.columns())
        df = dataframe[CacheMonitorColumn.columns()]
        for col in CacheMonitorColumn.columns():
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(-1).astype(int)
        return df

    def start(self) -> bool:
        """Start the sniffer by registering a subscriber to CacheMonitor."""
        if self._subscription_name is not None:
            LOGGER.warning(
                "CacheSniffer already started with subscription %s",
                self._subscription_name,
            )
            return True

        retry_count = 3
        for _ in range(retry_count):
            try:
                self._subscription_name = f"cache_sniffer_{uuid.uuid4()}"
                self._monitor.register_subscriber(
                    self._subscription_name,
                    self._record_df,
                    enable_override=False,
                )
                break
            except ValueError:
                LOGGER.warning(
                    "Retrying subscription %s...",
                    self._subscription_name,
                )
                self._subscription_name = None
        return self._subscription_name is not None

    def stop(self) -> None:
        if self._subscription_name is not None:
            self._monitor.unregister_subscriber(self._subscription_name)
        self._subscription_name = None
        self._update_dataframe()

    def _record_df(self, df: pd.DataFrame) -> None:
        with self._record_lock:
            self._records.append(df)

    def _update_dataframe(self) -> pd.DataFrame:
        """Merge buffered records into the cached dataframe."""
        with self._record_lock:
            update_records = self._records
            self._records = []

        if not update_records:
            return self._cache_df

        update_df = self._preprocess_df(pd.concat(update_records, ignore_index=True))
        self._cache_df = pd.concat([self._cache_df, update_df], ignore_index=True)
        # 剪除旧数据
        if CacheMonitorColumn.WINDOW_END_NS in update_df.columns:
            last_timestamp = update_df[CacheMonitorColumn.WINDOW_END_NS].max()
            minimum_timestamp = (
                last_timestamp
                - self._config.maximum_dataframe_size_in_seconds
                * TimeConstants.SEC2NANOSEC
            )
            self._cache_df = self._cache_df[
                self._cache_df[CacheMonitorColumn.WINDOW_END_NS] > minimum_timestamp
            ]

        # 聚合重复条目
        self._cache_df = self._aggregate_cache_misses(self._cache_df)
        return self._cache_df

    @classmethod
    def _aggregate_cache_misses(cls, dataframe: pd.DataFrame) -> pd.DataFrame:
        return (
            dataframe.groupby(
                [
                    CacheMonitorColumn.CPU,
                    CacheMonitorColumn.TGID,
                    CacheMonitorColumn.PID,
                ],
                as_index=False,
            )
            .agg(
                {
                    CacheMonitorColumn.TOTAL: "sum",
                    CacheMonitorColumn.L1I: "sum",
                    CacheMonitorColumn.LLC: "sum",
                    CacheMonitorColumn.WINDOW_START_NS: "min",
                    CacheMonitorColumn.WINDOW_END_NS: "max",
                }
            )
            .reset_index(drop=True)
        )

    def get_cache_df(self) -> pd.DataFrame:
        """Return the latest cache miss dataframe."""
        return self._update_dataframe()

    def get_cache_miss_by_tgid(self, tgid: int) -> pd.DataFrame:
        """Get aggregated cache miss info for a given tgid."""
        df = self.get_cache_df()
        return df[df[CacheMonitorColumn.TGID] == tgid]

    def get_cache_miss_by_tid(self, tid: int) -> pd.DataFrame:
        """Get aggregated cache miss info for a given tid."""
        df = self.get_cache_df()
        # light weight process
        tid_df = df[df[CacheMonitorColumn.PID] == tid]
        return tid_df[tid_df[CacheMonitorColumn.TGID] == tid]

    @property
    def cache_df_columns(self) -> list[str]:
        """Get list of all cache sniffer dataframe columns."""
        return CacheMonitorColumn.columns()

    @classmethod
    def get_cache_miss_stats_from_df(
        cls, dataframe: pd.DataFrame
    ) -> CacheMissStats | None:
        """Aggregate a cache miss dataframe into NUMA-level miss statistics."""
        deployment = StaticNumaDeployment()
        all_numa_ids = sorted(deployment.numa_nodes.keys())
        if dataframe.empty:
            return None

        df = dataframe.copy()
        df["numa_id"] = df[CacheMonitorColumn.CPU].map(deployment.cpu_to_numa)
        df = df.dropna(subset=["numa_id"])
        if df.empty:
            return None
        grouped = (
            df.groupby("numa_id", as_index=True)
            .agg(
                {
                    CacheMonitorColumn.TOTAL: "sum",
                    CacheMonitorColumn.L1I: "sum",
                    CacheMonitorColumn.LLC: "sum",
                }
            )
            .sort_index()
        )
        return CacheMissStats(
            all_numa_ids=all_numa_ids,
            numa_id_to_l1i_miss=grouped[CacheMonitorColumn.L1I].astype(int).to_dict(),
            numa_id_to_llc_miss=grouped[CacheMonitorColumn.LLC].astype(int).to_dict(),
            numa_id_to_total_miss=grouped[CacheMonitorColumn.TOTAL].astype(int).to_dict(),
        )

    def get_cache_miss_stats_by_pid(self, pid: int) -> CacheMissStats:
        """Return NUMA-aggregated cache miss info for a process PID/TGID."""
        return self.get_cache_miss_stats_from_df(self.get_cache_miss_by_tgid(pid))

    def get_cache_miss_stats_by_tid(self, tid: int) -> CacheMissStats:
        """Return NUMA-aggregated cache miss info for a thread PID/TID."""
        return self.get_cache_miss_stats_from_df(self.get_cache_miss_by_tid(tid))


def get_cache_sniffer(dataframe: Optional[pd.DataFrame] = None) -> CacheSniffer:
    """Get the default cache sniffer instance."""
    return CacheSniffer(dataframe=dataframe)


__all__ = ["CacheSniffer", "get_cache_sniffer"]


if __name__ == "__main__":
    sniffer = get_cache_sniffer()
    sniffer.start()
    time.sleep(5)
    sniffer.stop()
    LOGGER.info("collected df: \n%s", sniffer.get_cache_df())
