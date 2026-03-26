"""Structural relationship edges for entities.

Defines directed edges that represent ownership, containment, and access
relationships between entities. Used to model structural dependencies
distinct from data flow (e.g., "process has socket").

Edge Types:
    - OwnEdge: A "has" B (source owns/contains target)
        Example: Process → Socket (process has listening socket)
    - BelongEdge: A "belongs to" B (source is part of target)
        Example: Socket → Process (socket belongs to process)
        Inverse of OwnEdge
    - AccessEdge: A "accesses" B (source reads/writes target)
        Example: Process → SharedMemory (process accesses memory region)

Relationship Modeling:
    OwnEdge and BelongEdge typically model the same relationship from
    opposite directions:
        OwnEdge(process, socket) ≡ BelongEdge(socket, process)

    AccessEdge models explicit access patterns (read/write) distinct
    from ownership relationships.

Usage:
    ```python
    # Process owns a listening socket
    has_edge = OwnEdge(
        source_node=ProcessEntity(pid=100),
        target_node=SocketEntity(socket_port=18090)
    )

    # Socket belongs to process (inverse)
    belong_edge = BelongEdge(
        source_node=SocketEntity(socket_port=18090),
        target_node=ProcessEntity(pid=100)
    )

    # Process accesses shared memory
    access_edge = AccessEdge(
        source_node=ProcessEntity(pid=100),
        target_node=SharedMemoryEntity(shm_name="my_shm")
    )
    ```

Notes:
    All edge types are DirectedEdge subclasses with explicit source/target.
    Used by collectors to model structural relationships in topology.
"""

from witty_profiler.edge.edge_category import (
    DataStreamEdge,
    DeployEdge,
    DeployEdgeC2P,
    DeployEdgeP2C,
)


class OwnEdge(DeployEdgeP2C):
    """
    Edge representing a "has" relationship between entities

    ``OwnEdge(source_node=A, target_node=B)`` means A has B
    """


class BelongEdge(DeployEdgeC2P):
    """
    Edge representing a "belong to" relationship between entities

    ``BelongEdge(source_node=A, target_node=B)`` means A belongs to B
    """


class AccessEdge(DataStreamEdge):
    """
    Edge representing an "access" relationship between entities

    ``AccessEdge(source_node=A, target_node=B)`` means A accesses B
    """


class RunOnEdge(DeployEdgeC2P):
    """
    Edge representing a "run on" relationship between entities

    ``RunOnEdge(source_node=A, target_node=B)`` means A is run on B
        e.g., Process → DockerContainer (process runs on container)
    """

    pass


class HostEdge(DeployEdgeP2C):
    """
    Edge representing a "hosts" relationship between entities

    ``HostEdge(source_node=A, target_node=B)`` means A hosts B
        e.g., HostMachine → DockerContainer (host machine hosts container)
    """

    pass


__all__ = ["OwnEdge", "BelongEdge", "AccessEdge", "RunOnEdge", "HostEdge"]
