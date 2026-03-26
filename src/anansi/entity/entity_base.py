"""Provide entity abstraction and factory for topology graph nodes.

Manages process/thread nodes in the topology graph with automatic global ID
deduplication via GlobalIDManager and namespace scoping via EntityNameSpace.

Core Classes:
    - Entity: Base class for graph nodes; requires subclasses to implement unique_id property
    - EntityMeta: Metaclass for auto-registration and dataclass wrapping of entity subclasses
    - EntityFactory: Singleton factory for entity creation with global ID deduplication

Global ID Format:
    Global IDs are immutable and follow the pattern: [namespace]{entity_type}_{unique_id}
    Example: [process_collector]ProcessEntity_1234

Typical Workflow:
    1. Define custom entity by subclassing Entity and implementing unique_id property
    2. EntityMeta auto-registers the subclass in the registry
    3. Use EntityFactory.create_entity() to instantiate with automatic deduplication
    4. GlobalIDManager prevents duplicate entities with same global_id

Integration Points:
    - Depends on GlobalIDManager for global ID tracking and deduplication
    - Uses EntityNameSpace context manager for namespace-scoped creation
    - Integrates with graph Entity nodes for topology representation

Key Design Patterns:
    - Auto-registration via EntityMeta metaclass avoids manual registration
    - Dataclass wrapping enables automatic serialization (asdict/model_dump)
    - Global ID updates on attribute changes are handled transparently by GlobalIDManager
    - Namespace defaults to current EntityNameSpace.get_namespace() context value
"""

from abc import ABCMeta, abstractmethod
from dataclasses import asdict, dataclass, field

from anansi.common.constants import DEFAULT_NAMESPACE
from anansi.common.id_manager import GlobalIDManager, IdObject
from anansi.common.singleton import Singleton
from anansi.entity.entity_namespace import EntityNameSpace


class EntityMeta(ABCMeta):
    """Metaclass that registers entity subclasses and wraps them as dataclasses."""

    _entity_classes = {}

    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        if not hasattr(cls, "__abstractmethods__") or not cls.__abstractmethods__:
            # 记录类别映射
            mcs._entity_classes[name] = cls
        # 确保转为dataclass
        cls = dataclass(cls)
        return cls

    @classmethod
    def get_entity(mcs, name, default=None):
        return mcs._entity_classes.get(name, default)

    @classmethod
    def get_entity_names(mcs) -> list:
        return list(mcs._entity_classes.keys())


class Entity(IdObject, metaclass=EntityMeta):
    """Base class for all entities managed by the global ID registry."""

    entity_namespace: str = field(
        default_factory=lambda: EntityNameSpace.get_namespace()
    )
    entity_type: str = field(default_factory=lambda: "Entity")
    details: dict = field(default_factory=dict)

    def __post_init__(self):
        """Initialize entity after dataclass instantiation.

        Sets entity_type from class name and ensures entity_namespace is set from
        current EntityNameSpace context if initialized to DEFAULT_NAMESPACE.

        Example:
            with EntityNameSpace("192.168.122.1"):
                entity = ProcessEntity(pid=1234)
                # entity.entity_namespace will be "192.168.122.1"

        When a entity is passed from node A to node B and then to node C, the namespace
        will be set to the namespace of original node A:

        entity (namespace set to DEFAULT_NAMESPACE) in A
            --> serialized and sent to B
            --> deserialized in B in namespace context A (namespace set to A)
            --> sent to C
            --> deserialized in C in namespace context B (namespace still A)
        """
        self.entity_type = self.__class__.__name__
        if self.entity_namespace == DEFAULT_NAMESPACE:
            self.entity_namespace = EntityNameSpace.get_namespace()

    def reset_global_id(self):
        """Reset cached global ID to force re-computation on next access."""
        if hasattr(self, "_global_id_cache"):
            delattr(self, "_global_id_cache")
        if hasattr(self, "_str_cache"):
            delattr(self, "_str_cache")

    def __setattr__(self, name, value):
        if not hasattr(self, "_global_id_cache"):
            return super().__setattr__(name, value)
        old_id = self._global_id_cache
        ret = super().__setattr__(name, value)
        self.reset_global_id()
        manager: GlobalIDManager = GlobalIDManager.get_instance()
        if not manager.exists(old_id):  # old_id is not recorded
            return ret
        if old_id != self.global_id:  # global_id has changed, need to update registry
            manager.try_release_global_id(old_id)
            manager.record_or_get(self._global_id_cache, self)
        return ret

    @property
    def global_id(self) -> str:
        if not hasattr(self, "_global_id_cache"):
            if self.entity_namespace != DEFAULT_NAMESPACE:
                self._global_id_cache = "{}(ns={},{})".format(
                    self.entity_type_abbr, self.entity_namespace, self.unique_id
                )
            else:
                self._global_id_cache = "{}({})".format(
                    self.entity_type_abbr, self.unique_id
                )
        return self._global_id_cache

    def __str__(self) -> str:
        if not hasattr(self, "_str_cache"):
            # bypass dataclass-generated __str__ to avoid recursion, and cache the result
            object.__setattr__(self, "_str_cache", self._cachable_str())
        return self._str_cache

    def _cachable_str(self) -> str:
        """Get a string representation that will be cached and won't cause recursion."""
        return super().__str__()

    @property
    def entity_type_abbr(self) -> str:
        """Get abbreviated entity type (without namespace and unique ID)."""
        return self.entity_type.removesuffix("Entity")

    @property
    @abstractmethod
    def unique_id(self) -> str:
        """
        获取实体类别UID，例如：进程pid/线程tid
        """
        raise NotImplementedError

    def model_dump(self) -> dict:
        return asdict(self)


class EntityFactory(Singleton):
    """
    Singleton factory for entities
    """

    def create_entity(
        self, entity_data: dict | Entity, ensure_unique: bool = True
    ) -> Entity:
        """Create or retrieve an entity instance described by ``entity_data``."""
        entity = self._hard_create_entity(entity_data)
        if not ensure_unique:
            return entity
        manager: GlobalIDManager = GlobalIDManager.get_instance()
        entity, _ = manager.record_or_get(entity.global_id, entity)
        return entity

    def _hard_create_entity(self, entity_data: dict | Entity) -> Entity:
        """Instantiate an entity without checking for global-ID collisions."""
        if isinstance(entity_data, Entity):
            return entity_data

        entity_type = entity_data.get("entity_type")
        if entity_type is None:
            raise ValueError("entity_type is required")

        entity_cls = EntityMeta.get_entity(entity_type)
        if entity_cls is None:
            raise ValueError(
                f"Entity subclass '{entity_type}' not found. "
                f"(Available: {', '.join(EntityMeta.get_entity_names())})"
            )
        entity = entity_cls(**entity_data)
        return entity
