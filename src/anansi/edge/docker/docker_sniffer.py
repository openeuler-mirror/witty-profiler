import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

from anansi.entity.node_entity import ContainerEntity


class ContainerRuntime(str, Enum):
    DOCKER = "docker"
    CONTAINERD = "containerd"
    CRIO = "crio"
    UNKNOWN = "unknown"


class ContainerSniffer:
    """
    Sniffer to collect container topology information.
    Supports Docker, containerd (Kubernetes), and CRI-O.
    """

    # Regex patterns grouped by runtime for clarity
    _RUNTIME_PATTERNS = {
        ContainerRuntime.DOCKER: [
            re.compile(r"/docker/([a-f0-9]{64})"),
            re.compile(r"/docker-([a-f0-9]{64})\.scope"),
            re.compile(r"/snap\.docker\.dockerd/([a-f0-9]{64})"),
        ],
        ContainerRuntime.CRIO: [
            re.compile(r"/crio-([a-f0-9]{64})\.scope"),
        ],
        # containerd does not use prefixes; we detect it via context (e.g., kubepods)
        ContainerRuntime.CONTAINERD: [
            re.compile(r"/([a-f0-9]{64})(?:\.scope)?$"),
        ],
    }

    def get_container_by_pid(self, pid: int) -> Optional[ContainerEntity]:
        """
        Determine if a given host PID belongs to a container, and return its metadata.

        Supports:
          - Docker (standalone or legacy Kubernetes)
          - containerd (default in modern Kubernetes)
          - CRI-O

        Args:
            pid: Host process ID.

        Returns:
            ContainerEntity if the process runs inside a known container; otherwise None.
        """
        cgroup_content = self._read_cgroup_file(pid)
        if cgroup_content is None:
            return None

        # Try runtimes in order of specificity
        for runtime in [ContainerRuntime.DOCKER, ContainerRuntime.CRIO]:
            container_id = self._extract_container_id(cgroup_content, runtime)
            if container_id:
                return self._build_entity(container_id, runtime)

        # containerd requires contextual hint (e.g., "kubepods" in path)
        if "kubepods" in cgroup_content:
            container_id = self._extract_container_id(
                cgroup_content, ContainerRuntime.CONTAINERD
            )
            if container_id and self._is_valid_container_id(container_id):
                return self._build_entity(container_id, ContainerRuntime.CONTAINERD)

        return None

    def _read_cgroup_file(self, pid: int) -> Optional[str]:
        """Read /proc/<pid>/cgroup safely."""
        try:
            path = f"/proc/{pid}/cgroup"
            if not os.path.exists(path):
                return None
            with open(path, "r") as f:
                return f.read()
        except (OSError, IOError):
            return None

    def _extract_container_id(
        self, content: str, runtime: ContainerRuntime
    ) -> Optional[str]:
        """Attempt to extract a container ID for a given runtime."""
        patterns = self._RUNTIME_PATTERNS.get(runtime, [])
        for line in content.splitlines():
            for pattern in patterns:
                match = pattern.search(line)
                if match:
                    return match.group(1)
        return None

    def _is_valid_container_id(self, cid: str) -> bool:
        """Validate that the ID is a 64-character lowercase hex string."""
        return len(cid) == 64 and re.fullmatch(r"[a-f0-9]{64}", cid) is not None

    def _build_entity(
        self, container_id: str, runtime: ContainerRuntime
    ) -> ContainerEntity:
        """Construct a ContainerEntity with a human-readable name."""
        short_id = container_id[:12]
        name = f"{runtime.value}-{short_id}"
        return ContainerEntity(
            container_id=container_id,
            container_name=name,
            container_type=runtime.value,
        )
