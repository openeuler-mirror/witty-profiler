from witty_profiler.edge.edge_category import DataStreamEdge


class ConnectToEdge(DataStreamEdge):
    """
    Edge representing a "connect to" relationship between entities

    ``ConnectTo(source_node=A, target_node=B)`` means A connects to B
    """


__all__ = ["ConnectToEdge"]
