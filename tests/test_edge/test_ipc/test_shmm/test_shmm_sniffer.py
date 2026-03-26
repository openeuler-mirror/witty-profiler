import json
import logging
import os
import time
import unittest
from unittest import TestCase

from anansi.common.logging import get_logger
from anansi.common.worker_context import ProcessContextManager
from anansi.edge.shared_memory.shmm_sniffer import get_shared_memory_sniffer
from anansi.edge.structual.belong import AccessEdge
from anansi.entity.node_entity import ProcessEntity, SharedMemoryEntity
from anansi.graph.graph import Graph
from tests.test_edge.test_shmm.shmm_generator import (
    shmm_graph_start,
    wait_for_condition,
)

LOGGER = get_logger(__name__)

GROUND_TRUTH_GRAPH_FILE = os.path.join(
    os.path.dirname(__file__), "local", "ground_truth.json"
)


def load_ground_truth() -> Graph:

    with open(GROUND_TRUTH_GRAPH_FILE, "r") as f:
        ground_truth = Graph(**json.load(f))
    # LOGGER.info("Loaded ground truth graph:\n%s", ground_truth.describe())
    return ground_truth


def generate_shmm():
    if os.path.exists(GROUND_TRUTH_GRAPH_FILE):
        os.remove(GROUND_TRUTH_GRAPH_FILE)
    logger = get_logger(name=None)
    logger.setLevel(logging.ERROR)
    shmm_graph_start(
        num_processes=2,
        connection_probability=1.0,
        graph_file_path=GROUND_TRUTH_GRAPH_FILE,
        rounds=0,  # forever
        interval=1.0,
    )


class TestSharedMemorySniffer(TestCase):
    def setUp(self) -> None:
        if os.path.exists(GROUND_TRUTH_GRAPH_FILE):
            os.remove(GROUND_TRUTH_GRAPH_FILE)
        LOGGER.info(
            "Set up for TestSharedMemorySniffer, removed existing ground truth file."
        )
        self.sniffer = get_shared_memory_sniffer()

    def test_get_shared_memory_sniffer(self):
        with ProcessContextManager(generate_shmm) as proc:
            time.sleep(0.1)
            wait_for_condition(
                lambda: os.path.exists(GROUND_TRUTH_GRAPH_FILE),
                timeout=10,
                step=0.5,
            )
            LOGGER.info(
                "Shared memory graph generated: \n%s", load_ground_truth().describe()
            )
            graph = load_ground_truth()

            # 检查边
            for edge in graph.edges:
                if not isinstance(edge, AccessEdge):
                    continue
                if not (
                    isinstance(edge.source_node, ProcessEntity)
                    and isinstance(edge.target_node, SharedMemoryEntity)
                ):
                    continue
                src: ProcessEntity = edge.source_node
                tgt: SharedMemoryEntity = edge.target_node
                # 由shm名称查询pid
                pids = self.sniffer.query_pid_by_shm_name(tgt.shm_name)
                assert (
                    src.pid in pids
                ), f"PID {src.pid} not found in PIDs {pids} for SHM {tgt.shm_name}"

                # 由pid查询shm名称
                shm_names = self.sniffer.query_shm_by_pid(src.pid)
                self.assertIn(
                    tgt.shm_name,
                    shm_names,
                    f"SHM {tgt.shm_name} not found in SHMs {shm_names} for PID {src.pid}",
                )

    def test_query_shm_info_nonexistent(self):
        shm_info = self.sniffer.query_shm_info("non_existent_shm_name")
        self.assertIsNone(shm_info)
        pids = self.sniffer.query_pid_by_shm_name("non_existent_shm_name")
        self.assertEqual(pids, [])
        shm_names = self.sniffer.query_shm_by_pid(-1)  # Assuming this PID doesn't exist
        self.assertEqual(shm_names, [])


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestSharedMemorySniffer)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
