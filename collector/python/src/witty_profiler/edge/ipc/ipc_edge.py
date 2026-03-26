from witty_profiler.entity.node_entity import ProcessEntity
from witty_profiler.edge.edge import Edge, DirectedEdge
from dataclasses import field


class IPCEdge(DirectedEdge):
    """
    Edge representing an IPC relationship between entities

    ``IPCEdge(source_node=A, target_node=B)`` means A communicates with B via IPC
    """

    source_node: ProcessEntity = field(default=None)
    target_node: ProcessEntity = field(default=None)
