import glob
import logging
import os
import re
import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

from anansi.common.logging import get_logger
from anansi.config_manager.configs import NPUSnifferConfig
from anansi.entity.node_entity import NPUEntity, ProcessEntity

LOGGER = get_logger(__name__)


class NPUAccessSniffer(ABC):
    """NPU access sniffer abstraction.

    Read NPU access stats collected by the NPU access monitor, and expose
    query APIs for building topology graphs.
    """

    @classmethod
    def valid(cls) -> bool:
        if hasattr(cls, "_valid"):
            LOGGER.debug(f"Checking if {cls.__name__} is valid")
            return cls._valid

        try:
            instance = cls()
            instance.get_all_npu_entities()
            cls._valid = True
        except Exception as e:
            LOGGER.error("NPU access sniffer %s is not valid: %s", cls.__name__, e)
            cls._valid = False
        return cls._valid

    def __init__(self, config: Optional[NPUSnifferConfig] = None):
        self.config = config or NPUSnifferConfig()

    @abstractmethod
    def get_all_npu_entities(self) -> list[NPUEntity]:
        raise NotImplementedError

    @abstractmethod
    def get_npu_ranks_accessed_by_pid(self, pid: int) -> list[NPUEntity]:
        raise NotImplementedError

    @abstractmethod
    def get_pids_accessing_npu(self, npu_id: int) -> list[ProcessEntity]:
        raise NotImplementedError


class NoneNPUAccessSniffer(NPUAccessSniffer):
    def get_all_npu_entities(self) -> list[NPUEntity]:
        return []

    def get_npu_ranks_accessed_by_pid(self, pid: int) -> list[NPUEntity]:
        return []

    def get_pids_accessing_npu(self, npu_id: int) -> list[ProcessEntity]:
        return []


class AscendNPUAccessSniffer(NPUAccessSniffer):
    def __init__(self, config: Optional[NPUSnifferConfig] = None):
        self.config = config or NPUSnifferConfig()
        self._npu_entity_to_pids: Dict[NPUEntity, Set[int]] = {}
        self._last_update = 0

    def _parse_npu_smi_info(self) -> Dict[NPUEntity, Set[int]]:
        """
        Parse `npu-smi info` to extract:
          - NPU ID -> PCI Bus ID mapping (from device table)
          - NPU ID -> PIDs mapping (from process table)
        Returns: {NPUEntity(id, pci_bus_id): {pid1, pid2, ...}}
        """
        if time.time() - self._last_update < self.config.refresh_interval_by_second:
            return self._npu_entity_to_pids

        try:
            result = subprocess.run(
                ["npu-smi", "info"], capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                LOGGER.warning("npu-smi info failed")
                self._npu_entity_to_pids = {}
                self._last_update = time.time()
                return self._npu_entity_to_pids
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            LOGGER.warning(f"npu-smi not available: {e}. set to empty")
            self._npu_entity_to_pids = {}
            self._last_update = time.time()

            return self._npu_entity_to_pids

        lines = result.stdout.splitlines()

        # Step 1: Parse device table to get NPU ID -> PCI Bus ID
        npu_id_to_pci: Dict[int, str] = {}
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            # Match device line: "| 0     910B4 ..."
            if line.startswith("|") and re.search(r"\|\s*\d+\s+[A-Za-z0-9]", line):
                # Extract NPU ID from device line
                dev_match = re.search(r"\|\s*(\d+)\s+[A-Za-z0-9]", line)
                if not dev_match:
                    i += 1
                    continue
                npu_id = int(dev_match.group(1))

                # Next line should be PCI line
                if i + 1 < len(lines):
                    pci_line = lines[i + 1]
                    # Extract PCI Bus ID like "0000:C1:00.0"
                    pci_match = re.search(
                        r"([0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.0)", pci_line
                    )
                    if pci_match:
                        npu_id_to_pci[npu_id] = pci_match.group(1)
                i += 2  # Skip both device and PCI lines
            else:
                i += 1

        # Step 2: Parse process table (保持不变)
        npu_id_to_pids: Dict[int, Set[int]] = {}
        in_process_table = False
        for line in lines:
            if re.search(r"\|\s*NPU\s+Chip\s*\|.*Process id", line):
                in_process_table = True
                continue
            if not in_process_table:
                continue
            if "====" in line or "----" in line or not line.strip():
                continue
            match = re.search(r"\|\s*(\d+)\s+\d+\s*\|\s*(\d+)\s*\|", line)
            if match:
                npu_id = int(match.group(1))
                pid = int(match.group(2))
                if npu_id not in npu_id_to_pids:
                    npu_id_to_pids[npu_id] = set()
                npu_id_to_pids[npu_id].add(pid)

        # Step 3: Build final map
        npu_entity_to_pids: Dict[NPUEntity, Set[int]] = {}
        all_npu_ids = set(npu_id_to_pci.keys()) | set(npu_id_to_pids.keys())
        for npu_id in sorted(all_npu_ids):
            pci_bus_id = npu_id_to_pci.get(npu_id, "npu-pci-bus-id-unknown")
            npu_entity = NPUEntity.create_ensure_unique_id(
                id=npu_id, pci_bus_id=pci_bus_id
            )
            pids = npu_id_to_pids.get(npu_id, set())
            npu_entity_to_pids[npu_entity] = pids

        self._npu_entity_to_pids = npu_entity_to_pids
        self._last_update = time.time()
        return self._npu_entity_to_pids

    def get_all_npu_entities(self) -> List[NPUEntity]:
        """Get all NPU entities with id and pci_bus_id"""
        npu_map = self._parse_npu_smi_info()
        return list(npu_map.keys())

    def get_npu_ranks_accessed_by_pid(self, pid: int) -> List[NPUEntity]:
        """Get NPUEntity list accessed by given PID"""
        npu_map = self._parse_npu_smi_info()
        accessed = [npu for npu, pids in npu_map.items() if pid in pids]
        # Sort by NPU ID
        return sorted(accessed, key=lambda x: x.id)

    def get_pids_accessing_npu(self, npu: NPUEntity) -> List[ProcessEntity]:
        """Get PIDs accessing a specific NPU (match by id and pci_bus_id if possible)"""
        npu_map = self._parse_npu_smi_info()
        # Find matching NPUEntity (by id; pci_bus_id may be empty in input)
        for existing_npu, pids in npu_map.items():
            if existing_npu.id == npu.id:
                return [
                    ProcessEntity.create_ensure_unique_id(pid=p) for p in sorted(pids)
                ]
        return []


def get_npu_access_sniffer(
    config: Optional[NPUSnifferConfig] = None,
) -> NPUAccessSniffer:
    """Get the global NPU access sniffer instance."""
    config = config or NPUSnifferConfig()

    # 检查是否可用
    for sniffer_cls in [AscendNPUAccessSniffer, NoneNPUAccessSniffer]:
        if sniffer_cls.valid():
            LOGGER.info("Using NPU access sniffer: %s", sniffer_cls.__name__)
            return sniffer_cls(config=config)
    raise RuntimeError("No valid NPU access sniffer found")


if __name__ == "__main__":
    import argparse

    from anansi.config_manager.config_manager import GlobalConfigManager

    parser = argparse.ArgumentParser(description="Ascend NPU Access Sniffer")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # get-all-npus
    subparsers.add_parser("get-all-npus", help="List all NPU entities")

    # get-npus-by-pid
    parser_pid = subparsers.add_parser(
        "get-npus-by-pid", help="Get NPU IDs accessed by a given PID"
    )
    parser_pid.add_argument("pid", type=int, help="Process ID")

    # get-pids-by-npu
    parser_npu = subparsers.add_parser(
        "get-pids-by-npu", help="Get PIDs accessing a given NPU"
    )
    parser_npu.add_argument("npu_id", type=int, help="NPU ID (e.g., 0, 1, ...)")

    args = parser.parse_args()

    sniffer = AscendNPUAccessSniffer(
        config=GlobalConfigManager().get_config().sniffer_config.npu_sniffer
    )

    if args.command == "get-all-npus":
        npus = sniffer.get_all_npu_entities()
        print("Available NPU IDs:", [npu.id for npu in npus])
    elif args.command == "get-npus-by-pid":
        npus = sniffer.get_npu_ranks_accessed_by_pid(args.pid)
        print(f"PID {args.pid} accesses NPU IDs:", [npu.id for npu in npus])
    elif args.command == "get-pids-by-npu":
        npu_entity = NPUEntity.create_ensure_unique_id(id=args.npu_id)
        pids = sniffer.get_pids_accessing_npu(npu_entity)
        print(f"NPU {args.npu_id} is accessed by PIDs:", [p.pid for p in pids])
    else:
        parser.print_help()
