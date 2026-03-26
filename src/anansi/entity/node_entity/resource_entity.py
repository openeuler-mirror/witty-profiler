import os
import traceback
from typing import Dict, List, Optional

from anansi.common.logging import get_logger
from anansi.common.singleton import LOGGER
from anansi.common.str_converter import list_to_range_str, range_str_to_list
from anansi.entity.deployment.gpu_deployment import GPUDeploymentManager
from anansi.entity.deployment.npu_deployment import NPUDeploymentManager
from anansi.entity.entity_base import Entity, field

LOGGER = get_logger(__name__)


class ResourceEntity(Entity):
    """
    Entity representing a resource node
    """


class DeviceEntity(ResourceEntity):
    """
    Entity representing a device node
    """

    device_id: str = field(default_factory=lambda: "device-id-unknown")
    device_type: str = field(default_factory=lambda: "device-type-unknown")

    def __post_init__(self):
        super().__post_init__()
        self.device_id = str(self.device_id)

    @property
    def unique_id(self) -> str:
        return self.device_id


class GPUEntity(DeviceEntity):
    """
    Entity representing a GPU node
    """

    device_type: str = field(default_factory=lambda: "gpu")
    pci_bus_id: Optional[str] = field(default_factory=lambda: "gpu-pci-bus-id-unknown")
    id: int = field(default_factory=lambda: -1)
    cpu_affinity: str = field(default_factory=lambda: None)
    numa_affinity: str = field(default_factory=lambda: None)

    def __hash__(self):
        return hash((self.id))

    @property
    def unique_id(self) -> str:
        return f"id={self.id},pci_bus_id={self.pci_bus_id}"

    def __post_init__(self):
        super().__post_init__()
        if self.cpu_affinity is None:
            self.cpu_affinity = GPUDeploymentManager().query_gpu_cpu_affinity(self.id)
        if self.numa_affinity is None:
            self.numa_affinity = GPUDeploymentManager().query_gpu_numa_affinity(self.id)


class NPUEntity(DeviceEntity):
    """
    Entity representing a NPU node
    """

    device_type: Optional[str] = field(default_factory=lambda: "npu")
    pci_bus_id: Optional[str] = field(default_factory=lambda: "npu-pci-bus-id-unknown")
    id: int = field(default_factory=lambda: -1)
    cpu_affinity: str = field(default_factory=lambda: None)

    def __hash__(self):
        return hash((self.id))

    @property
    def unique_id(self) -> str:
        return "id={},cpu_affinity={}".format(self.id, self.cpu_affinity)

    def __post_init__(self):
        super().__post_init__()
        if self.cpu_affinity is None:
            self.cpu_affinity = NPUDeploymentManager().query_npu_cpu_affinity(self.id)


class SharedMemoryEntity(ResourceEntity):
    """
    Entity representing a shared memory node
    """

    shm_name: str = field(default_factory=lambda: "shm-name-unknown")
    shm_size: int = field(default_factory=lambda: -1)

    @property
    def unique_id(self) -> str:
        return f"name={self.shm_name},size={self.shm_size}"


class NumaEntity(ResourceEntity):
    numa_id: int = field(default_factory=lambda: -1)
    cpu_set: str = field(default_factory=lambda: None)
    memory_set: str = field(default_factory=lambda: None)
    numa_stats: Dict[str, int] = field(default_factory=dict)
    mem_info: Dict[str, str] = field(default_factory=dict)
    distance_to_all_numa: Dict[int, int] = field(default_factory=dict)

    def __post_init__(self):
        super().__post_init__()

    @property
    def unique_id(self) -> str:
        return f"numa{self.numa_id}"

    def _cachable_str(self) -> str:
        return f"[Numa {self.numa_id}](cpus={self.cpu_set},mems={self.memory_set},distance_to_all_numa={self.distance_to_all_numa})"


class NumaSetEntity(ResourceEntity):
    numa_id_str: str = field(default_factory=lambda: "")

    def __post_init__(self):
        super().__post_init__()

    @property
    def unique_id(self) -> str:
        return "{%s}" % (self.numa_id_str)


__all__ = [
    "ResourceEntity",
    "DeviceEntity",
    "GPUEntity",
    "NPUEntity",
    "SharedMemoryEntity",
    "NumaEntity",
    "NumaSetEntity",
]
