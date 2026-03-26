import json
from typing import Optional

from witty_profiler.common.logging import get_logger
from witty_profiler.common.singleton import Singleton
from witty_profiler.entity.entity_namespace import EntityNameSpace, EnvInfo
from witty_profiler.graph.graph import Graph

LOGGER = get_logger(__name__)


class GraphViewTool(Singleton):
    def view_graph(
        self,
        graph: Optional[Graph | dict],
        env: Optional[EnvInfo | dict] = None,
        output_file: Optional[str] = None,
    ):
        if isinstance(graph, Graph):
            graph: dict = graph.model_dump()
        if isinstance(env, dict):
            env = EnvInfo(**env)
        elif env is None:
            env = EnvInfo()
        with EntityNameSpace(env):
            # 重新构造Graph对象
            graph: Graph = Graph(**graph)

            if output_file is None:
                LOGGER.info("Graph: \n%s", graph.describe())
            else:
                with open(output_file, "wt", encoding="utf-8") as f:
                    f.write(graph.describe())

    def view_graph_from_file(self, file_path: str, output_file: Optional[str] = None):
        with open(file_path, "r", encoding="utf-8") as f:
            graph_data: dict = json.load(f)
            if "env" in graph_data:
                envinfo = EnvInfo(**graph_data["env"])
                graph_dict = graph_data.get("content", {})
            else:
                envinfo = EnvInfo()
                graph_dict = graph_data
            return self.view_graph(graph_dict, envinfo, output_file)
