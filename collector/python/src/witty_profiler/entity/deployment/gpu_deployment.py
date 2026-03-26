import os
import re
import subprocess

from witty_profiler.common.singleton import Singleton
from witty_profiler.common.str_converter import list_to_range_str


class GPUDeploymentManager(Singleton):
    def __init__(self):
        self.gpu2cpu_affinity: dict[int, str] = self._parse_cpu_affinity_by_id()
        self.gpu2numa_affinity: dict[int, str] = None

    def query_gpu_cpu_affinity(self, gpu_id: int) -> str:
        return self.gpu2cpu_affinity.get(gpu_id, "")

    def query_gpu_numa_affinity(self, gpu_id: int) -> str:
        if self.gpu2numa_affinity is None:
            self.gpu2numa_affinity = self._parse_numa_affinity_by_gpu_id()
        return self.gpu2numa_affinity.get(gpu_id, "")

    def trigger_update(self):
        self.gpu2cpu_affinity = self._parse_cpu_affinity_by_id()
        self.gpu2numa_affinity = self._parse_numa_affinity_by_gpu_id()

    def _parse_cpu_affinity_by_id(self) -> dict[int, str]:
        """
        Parse CPU affinity string via nvidia-smi and sysfs

        Returns:
            dict[int, str]: Mapping from GPU ID to its CPU affinity string.
                            Example: {0: "0-23", 1: "24-47", 2: "48-71", ...}
        """
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=index,pci.bus_id", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return {}

            affinity_map = {}
            lines = result.stdout.splitlines()

            for line in lines:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(", ")
                if len(parts) < 2:
                    continue

                gpu_id = int(parts[0].strip())
                pci_bus_id = parts[1].strip()

                cpu_affinity = self._get_cpu_affinity_from_pci(pci_bus_id)
                if cpu_affinity:
                    affinity_map[gpu_id] = cpu_affinity

            return affinity_map

        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return {}

    def _get_cpu_affinity_from_pci(self, pci_bus_id: str) -> str:
        """
        Get CPU affinity from PCI device via sysfs

        Args:
            pci_bus_id: PCI bus ID like "0000:01:00.0"

        Returns:
            str: CPU affinity string like "0-23" or "0,1,2,3"
        """
        try:
            pci_path = pci_bus_id.replace(":", "/").replace(".", "/")
            local_cpus_path = f"/sys/bus/pci/devices/{pci_bus_id}/local_cpus"

            if os.path.exists(local_cpus_path):
                with open(local_cpus_path, "r") as f:
                    content = f.read().strip()
                    return content

            return ""
        except Exception:
            return ""

    def _parse_numa_affinity_by_gpu_id(self) -> dict[int, str]:
        """
        Parse NUMA affinity string via nvidia-smi and sysfs

        Returns:
            dict[int, str]: Mapping from GPU ID to its NUMA affinity string.
                            Example: {0: "0", 1: "1", 2: "2", ...}
        """
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=index,pci.bus_id", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return {}

            numa_affinity_map = {}
            lines = result.stdout.splitlines()

            for line in lines:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(", ")
                if len(parts) < 2:
                    continue

                gpu_id = int(parts[0].strip())
                pci_bus_id = parts[1].strip()

                numa_affinity = self._get_numa_affinity_from_pci(pci_bus_id)
                if numa_affinity:
                    numa_affinity_map[gpu_id] = numa_affinity

            return numa_affinity_map

        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return {}

    def _get_numa_affinity_from_pci(self, pci_bus_id: str) -> str:
        """
        Get NUMA affinity from PCI device via sysfs

        Args:
            pci_bus_id: PCI bus ID like "0000:01:00.0"

        Returns:
            str: NUMA node ID like "0" or "1"
        """
        try:
            numa_node_path = f"/sys/bus/pci/devices/{pci_bus_id}/numa_node"

            if os.path.exists(numa_node_path):
                with open(numa_node_path, "r") as f:
                    content = f.read().strip()
                    return content

            return ""
        except Exception:
            return ""
