import re
import subprocess

from witty_profiler.common.singleton import Singleton
from witty_profiler.common.str_converter import list_to_range_str


class NPUDeploymentManager(Singleton):
    def __init__(self):
        self.npu2cpu_affinity: dict[int, str] = self._parse_cpu_affinity_by_id()
        self.npu2numa_affinity: dict[int, list[int]] = None  # lazy load

    def query_npu_cpu_affinity(self, npu_id: int) -> str:
        return self.npu2cpu_affinity.get(npu_id, "")

    def query_npu_numa_affinity(self, npu_id: int) -> str:
        if self.npu2numa_affinity is None:
            self.npu2numa_affinity = self._parse_numa_affinity_by_npu_id()
        return self.npu2numa_affinity.get(npu_id, "")

    def trigger_update(self):
        self.npu2cpu_affinity = self._parse_cpu_affinity_by_id()
        self.npu2numa_affinity = self._parse_numa_affinity_by_npu_id()

    def _parse_cpu_affinity_by_id(self) -> dict[int, str]:
        """
        Parse CPU affinity string via `npu-smi info -t topo`

        Returns:
            dict[int, str]: Mapping from NPU ID to its CPU affinity string.
                            Example: {0: "144-167", 1: "144-167", 2: "96-119", ...}
        """
        try:
            result = subprocess.run(
                ["npu-smi", "info", "-t", "topo"],
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
                # Match lines that start with "NPU<digits> "
                match = re.match(r"^NPU(\d+)\s+", line)
                if match:
                    npu_id = int(match.group(1))
                    # Split the line and get the last non-empty field (CPU Affinity column)
                    parts = line.split()
                    if parts:
                        cpu_affinity = parts[-1]
                        # Validate format: should be digit, hyphen, or comma (e.g., "0-23", "1,3-5")
                        if re.fullmatch(r"[\d,-]+", cpu_affinity):
                            affinity_map[npu_id] = cpu_affinity

            return affinity_map

        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return {}

    def _parse_numa_affinity_by_npu_id(self) -> dict[int, str]:
        """
        Parse NUMA affinity string via `npu-smi info -t topo`

        Returns:
            dict[int, str]: Mapping from NPU ID to its NUMA affinity string.
                            Example: {0: "0", 1: "0,2", 2: "2-3", ...}
        """
        from witty_profiler.edge.cpu.numa_deployment import StaticNumaDeployment

        npu2numa_affinity = {}
        npu2cpu_affinity = self._parse_cpu_affinity_by_id()
        for npu_id, cpu_affinity in npu2cpu_affinity.items():
            npu2numa_affinity[npu_id] = list_to_range_str(
                StaticNumaDeployment().query_numa_id_by_cpu(cpu_affinity)
            )
        return npu2numa_affinity
