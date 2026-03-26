from witty_profiler.edge.edge import DirectedEdge


class DeployEdge(DirectedEdge):
    """
    Edge representing a "deploy" relationship between an entity and the entity it is deployed on

    ``DeployEdge(source_node=A, target_node=B)`` means A is deployed on B
    """


class DeployEdgeP2C(DirectedEdge):
    """
    Edge representing a "deploy" relationship between a parent entity and a child entity

    ``DeployEdgeP2C(source_node=A, target_node=B)`` means A is deployed on B, where A is a parent entity and B is a child entity
    """


class DeployEdgeC2P(DirectedEdge):
    """
    Edge representing a "deploy" relationship between a child entity and a parent entity

    ``DeployEdgeC2P(source_node=A, target_node=B)`` means A is deployed on B, where A is a child entity and B is a parent entity
    """


class DataStreamEdge(DirectedEdge):
    """
    Edge representing a "data stream" relationship between two entities

    ``DataStreamEdge(source_node=A, target_node=B)`` means A has a data stream to B
    """
