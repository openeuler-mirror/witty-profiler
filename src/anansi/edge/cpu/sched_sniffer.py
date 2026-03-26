"""Provide a lightweight sched sniffer wrapper over SchedMonitor output.

Standardizes scheduler runtime dataframe columns and exposes a minimal API for
consuming buffered records via SchedMonitor.

Notes:
        - Columns align with sched monitor binary output: pid/tgid/cpu/time.
        - Collection is delegated to SchedMonitor; this wrapper focuses on
          dataframe normalization and buffering.

注意事项:
        - 无
"""

import threading
import uuid
from typing import Optional

import pandas as pd

from anansi.common.constants import SchedMonitorColumn
from anansi.common.logging import get_logger
from anansi.common.singleton import Singleton
from anansi.config_manager.config_manager import GlobalConfigManager
from anansi.config_manager.configs import CPUSnifferConfig
from anansi.edge.cpu.numa_deployment import StaticNumaDeployment
from anansi.edge.cpu.sched_monitor import SchedMonitor, get_sched_monitor

LOGGER = get_logger(__name__)


class SchedSniffer(Singleton):
    """Sched sniffer backed by SchedMonitor output."""

    def __init__(self, dataframe: Optional[pd.DataFrame] = None):
        mngr: GlobalConfigManager = GlobalConfigManager.get_instance()
        self._config: CPUSnifferConfig = mngr.get_config().sniffer_config.cpu_sniffer
        self._sched_df: pd.DataFrame = self._preprocess_df(dataframe)
        self._monitor: SchedMonitor = get_sched_monitor()
        self._subscription_name: Optional[str] = None
        self._records: list[pd.DataFrame] = []
        self._record_lock = threading.RLock()

    def _preprocess_df(self, dataframe: Optional[pd.DataFrame]) -> pd.DataFrame:
        if dataframe is None or dataframe.empty:
            return pd.DataFrame(columns=SchedMonitorColumn.columns())
        columns = dataframe.columns.tolist()
        for col in SchedMonitorColumn.columns():
            if col not in columns:
                LOGGER.error(
                    "SchedSniffer: missing required column '%s' in sniffer data", col
                )
                return pd.DataFrame(columns=SchedMonitorColumn.columns())
        df = dataframe[SchedMonitorColumn.columns()]
        for col in SchedMonitorColumn.columns():
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(-1).astype(int)
        return df

    def start(self) -> bool:
        """Start the sniffer by registering a subscriber to SchedMonitor."""
        if self._subscription_name is not None:
            LOGGER.warning(
                "SchedSniffer already started with subscription %s",
                self._subscription_name,
            )
            return True

        retry_count = 3
        for _ in range(retry_count):
            try:
                self._subscription_name = f"sched_sniffer_{uuid.uuid4()}"
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
            return self._sched_df

        update_df = self._preprocess_df(pd.concat(update_records, ignore_index=True))
        self._sched_df = pd.concat([self._sched_df, update_df], ignore_index=True)
        self._sched_df = self._aggregate_sched_time(self._sched_df)
        return self._sched_df

    @classmethod
    def _aggregate_sched_time(cls, dataframe: pd.DataFrame) -> pd.DataFrame:
        if dataframe.empty:
            return dataframe
        return (
            dataframe.groupby(
                [
                    SchedMonitorColumn.PID,
                    SchedMonitorColumn.TGID,
                    SchedMonitorColumn.CPU,
                ],
                as_index=False,
            )
            .agg({SchedMonitorColumn.TIME_NS: "sum"})
            .reset_index(drop=True)
        )

    def get_sched_df(self) -> pd.DataFrame:
        """Return the latest sched runtime dataframe."""
        return self._update_dataframe()

    def get_sched_df_by_tgid(self, tgid: int) -> pd.DataFrame:
        """Return the sched runtime dataframe filtered by TGID."""
        df = self.get_sched_df()
        return df[df[SchedMonitorColumn.TGID] == tgid].reset_index(drop=True)

    def get_sched_df_by_pid(self, pid: int) -> pd.DataFrame:
        """Return the sched runtime dataframe filtered by PID."""
        df = self.get_sched_df()
        return df[df[SchedMonitorColumn.PID] == pid].reset_index(drop=True)

    def get_numa_cpu_time_by_pid(self, pid: int) -> dict[int, float]:
        """Get the CPU time spent on each NUMA node by the given PID."""
        df = self.get_sched_df_by_pid(pid)
        deployment = StaticNumaDeployment()
        df["numa_id"] = df[SchedMonitorColumn.CPU].map(deployment.cpu_to_numa)
        numa_cpu_time = (
            df.groupby("numa_id")
            .agg({SchedMonitorColumn.TIME_NS: "sum"})
            .to_dict()[SchedMonitorColumn.TIME_NS]
        )
        return {numa_id: float(time_ns) for numa_id, time_ns in numa_cpu_time.items()}

    def get_numa_cpu_time_by_tgid(self, tgid: int) -> dict[int, float]:
        """Get the CPU time spent on each NUMA node by the given TGID."""
        df = self.get_sched_df_by_tgid(tgid)
        deployment = StaticNumaDeployment()
        df["numa_id"] = df[SchedMonitorColumn.CPU].map(deployment.cpu_to_numa)
        numa_cpu_time = (
            df.groupby("numa_id")
            .agg({SchedMonitorColumn.TIME_NS: "sum"})
            .to_dict()[SchedMonitorColumn.TIME_NS]
        )
        return {numa_id: float(time_ns) for numa_id, time_ns in numa_cpu_time.items()}


def get_sched_sniffer(dataframe: Optional[pd.DataFrame] = None) -> SchedSniffer:
    """Get the default sched sniffer instance."""
    return SchedSniffer(dataframe=dataframe)


__all__ = ["SchedSniffer", "get_sched_sniffer"]


if __name__ == "__main__":
    import time

    sched_sniffer = get_sched_sniffer()
    sched_sniffer.start()
    time.sleep(5)
    sched_sniffer.stop()
    df = sched_sniffer.get_sched_df()
    LOGGER.info("collected df: \n%s", df)
