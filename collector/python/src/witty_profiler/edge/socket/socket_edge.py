"""Socket communication edge and data flow statistics.

Defines SocketEdge (directed edge for socket communication) and DataFlowStats
(aggregatable metrics for socket flows). SocketEdge connects a source process
to a destination socket, representing active data transfers.

Key Components:
    - SocketEdge: Directed edge from ProcessEntity to SocketEntity
    - DataFlowStats: Metrics for a single socket flow (bytes, packets)

DataFlowStats:
    Tracks aggregate communication statistics per socket flow:
    - data_size: Total bytes transferred
    - packets_cnt: Total packets/messages sent
    - merge_other(): Accumulates statistics from duplicate edges

SocketEdge:
    Represents process → socket communication with:
    - source_node: ProcessEntity initiating communication
    - target_node: SocketEntity receiving communication
    - connection_type: TCP or UDP
    - weight: Optional aggregation metric (inherited from Edge)

Usage:
    ```python
    # Create socket communication edge
    edge = SocketEdge(
        source_node=ProcessEntity(pid=100),
        target_node=SocketEntity(
            socket_addr="127.0.0.1",
            socket_port=18090
        ),
        connection_type="TCP"
    )

    # Aggregate statistics when duplicate edges found
    stats1 = DataFlowStats(data_size=1024, packets_cnt=10)
    stats2 = DataFlowStats(data_size=2048, packets_cnt=20)
    stats1.merge_other(stats2)  # stats1 now has 3072 bytes, 30 packets
    ```

Notes:
    DataFlowStats.merge_other() validates type before merging.
    SocketEdge inherits from DirectedEdge for explicit source/target tracking.
"""

from dataclasses import dataclass, field

from witty_profiler.common.constants import CONNECTION_TYPE_TCP, TimeConstants
from witty_profiler.edge.edge_category import DataStreamEdge
from witty_profiler.entity.node_entity import ProcessEntity, SocketEntity, ThreadEntity


@dataclass
class DataFlowStats:
    start_time: float = -1
    end_time: float = -1
    data_size: int = 0
    packets_cnt: int = 0

    def merge_other(self, other: "DataFlowStats") -> "DataFlowStats":
        if not isinstance(other, DataFlowStats):
            raise ValueError("Can only merge with another DataFlowStats instance")
        self.data_size += other.data_size
        self.packets_cnt += other.packets_cnt

        self.end_time = max(self.end_time, other.end_time)
        self.start_time = min(self.start_time, other.start_time)
        return self

    def __str__(self):
        return "total:data_size={},packets_cnt={} (in {} seconds)".format(
            self.data_size,
            self.packets_cnt,
            (self.end_time - self.start_time) / TimeConstants.SEC2NANOSEC,
        )


class SendToSocketEdge(DataStreamEdge):
    """
    边表示socket通信
    """

    connection_type: str = field(default_factory=lambda: CONNECTION_TYPE_TCP)
    source_node: ProcessEntity | ThreadEntity = field(default=None)
    target_node: SocketEntity = field(default=None)
    data_flow: DataFlowStats = field(default_factory=DataFlowStats)

    def merge_other(self, other: "SendToSocketEdge") -> "SendToSocketEdge":
        if not isinstance(other, SendToSocketEdge):
            raise ValueError("Cannot merge SocketEdge with non-SocketEdge")
        if type(self.source_node) != type(other.source_node):
            raise ValueError("Cannot merge SocketEdge with different source node types")

        super().merge_other(other)
        self.data_flow.merge_other(other.data_flow)
        return self

    def __str__(self):
        return super().__str__() + f"({self.data_flow})"


__all__ = ["SendToSocketEdge", "DataFlowStats"]
