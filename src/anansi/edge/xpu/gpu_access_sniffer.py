import logging
import re
import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

from anansi.common.logging import get_logger
from anansi.config_manager.configs import GPUSnifferConfig
from anansi.entity.node_entity import GPUEntity, ProcessEntity

LOGGER = get_logger(__name__)


class GPUAccessSniffer(ABC):
    """GPU access sniffer abstraction.

    Read GPU access stats collected by the GPU access monitor, and expose
    query query APIs for building topology graphs.
    """

    @classmethod
    def valid(cls) -> bool:
        if hasattr(cls, "_valid"):
            LOGGER.debug(f"Checking if {cls.__name__} is valid")
            return cls._valid

        try:
            instance = cls()
            instance.get_all_gpu_entities()
            cls._valid = True
        except Exception as e:
            LOGGER.error("GPU access sniffer %s is not valid: %s", cls.__name__, e)
            cls._valid = False
        return cls._valid

    def __init__(self, config: Optional[GPUSnifferConfig] = None):
        self.config = config or GPUSnifferConfig()

    @abstractmethod
    def get_all_gpu_entities(self) -> List[GPUEntity]:
        raise NotImplementedError

    @abstractmethod
    def get_gpu_ranks_accessed_by_pid(self, pid: int) -> List[GPUEntity]:
        raise NotImplementedError

    @abstractmethod
    def get_pids_accessing_gpu(self, gpu: GPUEntity) -> List[ProcessEntity]:
        raise NotImplementedError


class NoneGPUAccessSniffer(GPUAccessSniffer):
    def get_all_gpu_entities(self) -> List[GPUEntity]:
        return []

    def get_gpu_ranks_accessed_by_pid(self, pid: int) -> List[GPUEntity]:
        return []

    def get_pids_accessing_gpu(self, gpu: GPUEntity) -> List[ProcessEntity]:
        return []


class NVIDIAGPUAccessSniffer(GPUAccessSniffer):
    def __init__(self, config: Optional[GPUSnifferConfig] = None):
        self.config = config or GPUSnifferConfig()
        self._gpu_entity_to_pids: Dict[GPUEntity, Set[int]] = {}
        self._last_update = 0

    def _parse_nvidia_smi_info(self) -> Dict[GPUEntity, Set[int]]:
        """
        Parse `nvidia-smi` to extract:
          - GPU ID -> PCI Bus ID mapping (from device table)
          - GPU ID -> PIDs mapping (from process table)
        Returns: {GPUEntity(id, pci_bus_id): {pid1, pid2, ...}}
        """
        if time.time() - self._last_update < self.config.refresh_interval_by_second:
            return self._gpu_entity_to_pids

        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=index,uuid,pci.bus_id", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                LOGGER.warning("nvidia-smi query-gpu failed")
                self._gpu_entity_to_pids = {}
                self._last_update = time.time()
                return self._gpu_entity_to_pids
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            LOGGER.warning(f"nvidia-smi not available: {e}. set to empty")
            self._gpu_entity_to_pids = {}
            self._last_update = time.time()
            return self._gpu_entity_to_pids

        lines = result.stdout.splitlines()

        gpu_id_to_pci: Dict[int, str] = {}
        for line in lines:
            line = line.strip()
            if not line:
                continue
            parts = line.split(", ")
            if len(parts) >= 3:
                gpu_id = int(parts[0].strip())
                pci_bus_id = parts[2].strip()
                gpu_id_to_pci[gpu_id] = pci_bus_id

        gpu_id_to_pids: Dict[int, Set[int]] = {}
        try:
            result_pmon = subprocess.run(
                ["nvidia-smi", "pmon", "-c", "1", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result_pmon.returncode == 0:
                for line in result_pmon.stdout.splitlines():
                    line = line.strip()
                    if not line or "GPU" in line:
                        continue
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 2:
                        try:
                            gpu_id = int(parts[0])
                            pid_str = parts[1]
                            if pid_str and pid_str != "-":
                                pid = int(pid_str)
                                if gpu_id not in gpu_id_to_pids:
                                    gpu_id_to_pids[gpu_id] = set()
                                gpu_id_to_pids[gpu_id].add(pid)
                        except (ValueError, IndexError):
                            continue
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            LOGGER.warning(f"nvidia-smi pmon failed: {e}")

        gpu_entity_to_pids: Dict[GPUEntity, Set[int]] = {}
        all_gpu_ids = set(gpu_id_to_pci.keys()) | set(gpu_id_to_pids.keys())
        for gpu_id in sorted(all_gpu_ids):
            pci_bus_id = gpu_id_to_pci.get(gpu_id, "gpu-pci-bus-id-unknown")
            gpu_entity = GPUEntity.create_ensure_unique_id(id=gpu_id, pci_bus_id=pci_bus_id)
            pids = gpu_id_to_pids.get(gpu_id, set())
            gpu_entity_to_pids[gpu_entity] = pids

        self._gpu_entity_to_pids = gpu_entity_to_pids
        self._last_update = time.time()
        return self._gpu_entity_to_pids

    def get_all_gpu_entities(self) -> List[GPUEntity]:
        """Get all GPU entities with id and pci_bus_id"""
        gpu_map = self._parse_nvidia_smi_info()
        return list(gpu_map.keys())

    def get_gpu_ranks_accessed_by_pid(self, pid: int) -> List[GPUEntity]:
        """Get GPUEntity list accessed by given PID"""
        gpu_map = self._parse_nvidia_smi_info()
        accessed = [gpu for gpu, pids in gpu_map.items() if pid in pids]
        return sorted(accessed, key=lambda x: x.id)

    def get_pids_accessing_gpu(self, gpu: GPUEntity) -> List[ProcessEntity]:
        """Get PIDs accessing a specific GPU (match by id and pci_bus_id if possible)"""
        gpu_map = self._parse_nvidia_smi_info()
        for existing_gpu, pids in gpu_map.items():
            if existing_gpu.id == gpu.id:
                return [
                    ProcessEntity.create_ensure_unique_id(pid=p) for p in sorted(pids)
                ]
        return []


def get_gpu_access_sniffer(
    config: Optional[GPUSnifferConfig] = None,
) -> GPUAccessSniffer:
    """Get the global GPU access sniffer instance."""
    config = config or GPUSnifferConfig()

    for sniffer_cls in [NVIDIAGPUAccessSniffer, NoneGPUAccessSniffer]:
        if sniffer_cls.valid():
            LOGGER.info("Using GPU access sniffer: %s", sniffer_cls.__name__)
            return sniffer_cls(config=config)
    raise RuntimeError("No valid GPU access sniffer found")


if __name__ == "__main__":
    import argparse

    from anansi.config_manager.config_manager import GlobalConfigManager

    parser = argparse.ArgumentParser(description="NVIDIA GPU Access Sniffer")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    subparsers.add_parser("get-all-gpus", help="List all GPU entities")

    parser_pid = subparsers.add_parser(
        "get-gpus-by-pid", help="Get GPU IDs accessed by a given PID"
    )
    parser_pid.add_argument("pid", type=int, help="Process ID")

    parser_gpu = subparsers.add_parser(
        "get-pids-by-gpu", help="Get PIDs accessing a given GPU"
    )
    parser_gpu.add_argument("gpu_id", type=int, help="GPU ID (e.g., 0, 1, ...)")

    args = parser.parse_args()

    sniffer = NVIDIAGPUAccessSniffer(
        config=GlobalConfigManager().get_config().sniffer_config.gpu_sniffer
    )

    if args.command == "get-all-gpus":
        gpus = sniffer.get_all_gpu_entities()
        print("Available GPU IDs:", [gpu.id for gpu in gpus])
    elif args.command == "get-gpus-by-pid":
        gpus = sniffer.get_gpu_ranks_accessed_by_pid(args.pid)
        print(f"PID {args.pid} accesses GPU IDs:", [gpu.id for gpu in gpus])
    elif args.command == "get-pids-by-gpu":
        gpu_entity = GPUEntity.create_ensure_unique_id(id=args.gpu_id)
        pids = sniffer.get_pids_accessing_gpu(gpu_entity)
        print(f"GPU {args.gpu_id} is accessed by PIDs:", [p.pid for p in pids])
    else:
        parser.print_help()
