from abc import ABC, ABCMeta, abstractmethod
from typing import Optional

from ..layout import Layout


class LayoutRendererMeta(ABCMeta):

    _registered_renderers = {}
    _legacy_registered_renderers = {}

    def __new__(mcls, name, bases, namespace, **kwargs):
        cls = super().__new__(mcls, name, bases, namespace, **kwargs)
        if not hasattr(cls, "__abstractmethods__") or not cls.__abstractmethods__:
            renderer_name = getattr(cls, "renderer_name", None) or name
            mcls._registered_renderers[renderer_name] = cls
            mcls._legacy_registered_renderers[name] = cls
        return cls

    @classmethod
    def get_renderer_class(mcls, name, default=None):
        renderer_cls = mcls._registered_renderers.get(name)
        if renderer_cls is not None:
            return renderer_cls
        return mcls._legacy_registered_renderers.get(name, default)

    @classmethod
    def available_renderers(mcls):
        return list(mcls._registered_renderers.keys())


def available_renderers():
    return LayoutRendererMeta.available_renderers()


def get_renderer_class(name, default=None) -> Optional["LayoutRenderer"]:
    return LayoutRendererMeta.get_renderer_class(name, default)


class LayoutRenderer(ABC, metaclass=LayoutRendererMeta):
    renderer_name: str | None = None

    def __init__(self, layout: Layout):
        self.layout = layout

    @abstractmethod
    def render(self) -> str:
        raise NotImplementedError("Subclasses must implement the render method.")


__all__ = ["LayoutRenderer", "available_renderers", "get_renderer_class"]
