from witty_profiler.common.id_manager import GlobalIDManager
from witty_profiler.edge.edge import DirectedEdge
from witty_profiler.entity.entity_base import Entity, EntityFactory


class HasAttributeEdge(DirectedEdge):
    """
    Edge representing an "has attribute" relationship between an entity and its attribute

    ``HasAttributeEdge(source_node=A, target_node=B)`` means A has attribute B
    """

    pass
