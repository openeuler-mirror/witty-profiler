from anansi.common.id_manager import GlobalIDManager
from anansi.edge.edge import DirectedEdge
from anansi.entity.entity_base import Entity, EntityFactory


class HasAttributeEdge(DirectedEdge):
    """
    Edge representing an "has attribute" relationship between an entity and its attribute

    ``HasAttributeEdge(source_node=A, target_node=B)`` means A has attribute B
    """

    pass
