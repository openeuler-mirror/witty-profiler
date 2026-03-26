from ..layout import Layout, LayoutElement
from .renderer_base import LayoutRenderer


class DefaultLayoutRenderer(LayoutRenderer):
    renderer_name = "default"

    def render(self) -> str:
        # For demonstration, we will just return a simple string representation of the layout.
        # In a real implementation, this would convert the layout into a specific format (e.g., DOT, JSON).
        ans = []
        ans.append("Default Layout Renderer Output (Structural):")
        self.explore_layout(self.layout.root, ans, level=0)
        return "\n".join(ans)

    def explore_layout(self, element: LayoutElement, ans: list[str], level: int):
        indent = "  " * level
        geo = f"x={element.x}, y={element.y}, w={element.w}, h={element.h}"
        ans.append(f"{indent}- {element} ({geo})")
        for child in element.deploy_children.values():
            self.explore_layout(child, ans, level + 1)
