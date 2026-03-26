import json
from abc import ABC, ABCMeta, abstractmethod

from witty_profiler.common.logging import get_logger
from witty_profiler.edge.edge_category import (
    DataStreamEdge,
    DeployEdgeC2P,
    DeployEdgeP2C,
    DirectedEdge,
)
from witty_profiler.graph.graph import Graph
from witty_profiler.visualize.layout.layout_element import LayoutElement

LOGGER = get_logger(__name__)


class LayoutMeta(ABCMeta):
    _registry = {}

    def __new__(cls, name, bases, namespace):
        cls = super().__new__(cls, name, bases, namespace)
        if not hasattr(cls, "__abstractmethods__") or not cls.__abstractmethods__:
            cls._registry[name] = cls
        return cls

    @classmethod
    def available_layouts(cls) -> list:
        return list(cls._registry.keys())

    @classmethod
    def get_layout_class(cls, name):
        return cls._registry.get(name, None)


class Layout(ABC, metaclass=LayoutMeta):
    """
    Layout represents the overall structure of the graph, including nodes and edges.
    It serves as a container for all entities and relationships in the graph.
    """

    def __init__(self):
        self.root: LayoutElement = LayoutElement(
            is_root=True
        )  # The root element of the layout

    @abstractmethod
    def build_from_graph(self, graph: Graph) -> "Layout":
        raise NotImplementedError


def get_layout_class(name: str) -> type[Layout]:
    return LayoutMeta.get_layout_class(name)


def available_layouts() -> list:
    return LayoutMeta.available_layouts()


__all__ = ["Layout", "get_layout_class", "available_layouts"]
