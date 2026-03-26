import glob
import os
import re
from typing import Dict, Optional

from witty_profiler.common.logging import get_logger
from witty_profiler.common.singleton import Singleton
from witty_profiler.common.str_converter import list_to_range_str, range_str_to_list
from witty_profiler.entity.node_entity import NumaEntity

LOGGER = get_logger(__name__)


class StaticNumaDeployment(Singleton):
    """Numa和CPU的静态部署信息"""

    def __init__(self):
        """初始构建"""

        self.numa_nodes: Dict[int, NumaEntity] = {}
        self.cpu_to_numa: Dict[int, int] = {}
        self.numa_distances: Dict[int, Dict[int, int]] = {}
        self.detect()

    def detect(self):
        """
        构建静态部署信息
        填充: self.numa_nodes, self.cpu_to_numa, self.numa_distances
        依赖于/sys/devices/system/node/目录下的numa节点信息
        依赖于`numactl -H`
        """
        self.numa_distances = self._parse_numa_distances()

        all_nodes = glob.glob("/sys/devices/system/node/node*")
        numa_ids = sorted(
            [
                int(os.path.split(node_path)[-1].lstrip("node"))
                for node_path in all_nodes
            ]
        )
        self.numa_nodes = {i: self._parse_numa_node(i) for i in numa_ids}
        self.cpu_to_numa = {
            cpu_id: numa_index
            for numa_index, numa_entity in self.numa_nodes.items()
            for cpu_id in range_str_to_list(numa_entity.cpu_set)
        }
        LOGGER.info(f"Detected NUMA deployment: %s", self.numa_nodes.keys())

    def _parse_numa_distances(self) -> Dict[int, Dict[int, int]]:
        """
        解析numa节点之间的距离信息
        依赖于`numactl -H`命令输出中的距离矩阵
        返回一个字典，键为`numa_id1`，值为另一个字典，键为`numa_id2`，值为对应的距离
        """
        output = os.popen("numactl -H").read()
        lines = output.splitlines()
        distance_matrix_started = False
        distances = {}
        for line in lines:
            if line.startswith("node distances:"):
                distance_matrix_started = True
                continue
            if distance_matrix_started:
                if line.startswith("node "):
                    continue  # 跳过行头
                if not line.strip():
                    break  # 距离矩阵结束
                parts = line.split()
                if len(parts) < 2:
                    continue
                numa_id = int(parts[0].rstrip(":"))
                for i, dist in enumerate(parts[1:]):
                    distances.setdefault(numa_id, {})[i] = int(dist)
                    distances.setdefault(i, {})[numa_id] = int(dist)  # 对称矩阵
        return distances

    def query_numa_id_by_cpu(self, cpu_list: list[int] | str) -> list[int]:
        if isinstance(cpu_list, str):
            cpu_list = range_str_to_list(cpu_list)

        ans = set()
        for cpu_id in cpu_list:
            numa_index = self.cpu_to_numa.get(cpu_id)
            if numa_index is None:
                continue
            ans.add(numa_index)

        return list(ans)

    def _parse_numa_node(self, node_index: int) -> Optional[NumaEntity]:
        node_path = f"/sys/devices/system/node/node{node_index}"
        if not os.path.exists(node_path):
            return None
        cpu_set = open(f"{node_path}/cpulist").read().strip()
        memory_blocks = [
            int(os.path.basename(e)[6:])
            for e in glob.glob(f"{node_path}/memory*")
            if re.match(r"^memory\d+$", os.path.basename(e))
        ]
        mem_info = self._get_mem_info(node_path)
        numa_stat = self._get_numa_stat(node_path)

        return NumaEntity(
            cpu_set=cpu_set,
            memory_set=list_to_range_str(memory_blocks),
            numa_id=node_index,
            numa_stats=numa_stat,
            mem_info=mem_info,
            distance_to_all_numa=self.numa_distances.get(node_index, {}),
        )

    @classmethod
    def _get_mem_info(cls, node_path: str) -> dict:
        meminfo = open(f"{node_path}/meminfo").read()
        meminfo_dict = {}
        for line in meminfo.splitlines():
            key, value = line.split(":")
            key = key.split()[-1]
            meminfo_dict[key.strip()] = value.strip()
        return meminfo_dict

    @classmethod
    def _get_numa_stat(cls, node_path: str) -> dict:
        stat = open(f"{node_path}/numastat").read()
        stat = {k: int(v) for k, v in re.findall(r"(\w+)\s+(\d+)", stat)}
        return stat

    def __str__(self) -> str:
        ans = "[Numa Deployment]\n"
        for k, v in self.numa_nodes.items():
            ans += f"{v}\n"
        return ans
