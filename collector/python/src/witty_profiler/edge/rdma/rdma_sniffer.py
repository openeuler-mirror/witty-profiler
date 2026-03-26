from typing import Optional

from witty_profiler.edge.rdma.rdma_monitor import (
    MRRecord,
    PDRecord,
    QPRecord,
    RDMAMonitor,
    RDMAStatistic,
)
from witty_profiler.entity.node_entity.rdma import (
    RdmaDevice,
    RdmaLocalQueuePair,
    RdmaMemoryRegion,
    RdmaProtectionDomain,
    RdmaStatisticPerSecond,
)


class RDMASniffer:
    def __init__(self):
        self._monitor = RDMAMonitor()
        self._pd_records_cache: list[PDRecord] = []
        self._qp_records_cache: list[QPRecord] = []
        self._mr_records_cache: list[MRRecord] = []
        self._update_cache()

    def start(self):
        self._monitor.start()

    def stop(self):
        self._monitor.stop()

    def clear(self):
        self._monitor.clear()
        self._update_cache()

    def _update_cache(self):
        self._pd_records_cache: list[PDRecord] = self._monitor.get_rdma_pd_records()
        self._qp_records_cache: list[QPRecord] = self._monitor.get_rdma_qp_records()
        self._mr_records_cache: list[MRRecord] = self._monitor.get_rdma_mr_records()

    def get_pds_by_pid(self, pid: int) -> list[RdmaProtectionDomain]:
        pds = []
        for record in self._pd_records_cache:
            if record.pid == pid:
                pd = RdmaProtectionDomain.create_ensure_unique_id(
                    pdn=record.pdn,
                    pid=record.pid,
                    dev=record.dev,
                )
                pds.append(pd)
        return pds

    def get_qps_by_pdn(
        self, pd_entity: RdmaProtectionDomain
    ) -> list[RdmaLocalQueuePair]:
        qps = []
        for record in self._qp_records_cache:
            if record.pdn == pd_entity.pdn and record.device == pd_entity.dev:
                qp = RdmaLocalQueuePair.create_ensure_unique_id(
                    qpn=record.lqpn,
                    pid=record.pid,
                    pdn=record.pdn,
                    dev=record.device,
                    port=record.port,
                    rqpn=record.rqpn,
                )
                qps.append(qp)
        return qps

    def get_mrs_by_pdn(self, pd_entity: RdmaProtectionDomain) -> list[RdmaMemoryRegion]:
        mrs = []
        for record in self._mr_records_cache:
            if record.pdn == pd_entity.pdn and record.device == pd_entity.dev:
                mr = RdmaMemoryRegion.create_ensure_unique_id(
                    lkey=record.lkey,
                    rkey=record.rkey,
                    mrlen=record.mrlen,
                    pdn=record.pdn,
                    pid=record.pid,
                )
                mrs.append(mr)
        return mrs

    def get_devices_by_pdn(self, pd_entity: RdmaProtectionDomain) -> list[RdmaDevice]:
        device = RdmaDevice.create_ensure_unique_id(dev=pd_entity.dev)
        return [device]

    def get_statistic_by_device(
        self, device_entity: RdmaDevice
    ) -> RdmaStatisticPerSecond:
        stats_per_second = self._monitor.get_statistics_per_second()
        for (dev, port), stat in stats_per_second.key2stat.items():
            if dev == device_entity.dev:
                return RdmaStatisticPerSecond(
                    dev=stat.dev,
                    port=stat.port,
                    send_pkts=stat.send_pkts,
                    recv_pkts=stat.recv_pkts,
                    dupl_pkts=stat.dupl_pkts,
                    rdma_sends=stat.rdma_sends,
                    rdma_recvs=stat.rdma_recvs,
                )
        return None

    def get_all_pid_accessing_rdma(self) -> list[int]:
        pids = set()
        for record in self._pd_records_cache:
            if record.valid():
                pids.add(record.pid)
        return list(pids)

    def get_qp_by_lqpn(self, lqpn: int) -> Optional[QPRecord]:
        for record in self._qp_records_cache:
            if record.lqpn == lqpn:
                return record
        return None

    def get_qp_by_rqpn(self, rqpn: int) -> Optional[QPRecord]:
        for record in self._qp_records_cache:
            if record.rqpn == rqpn:
                return record
        return None
