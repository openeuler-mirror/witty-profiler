from xml.sax.saxutils import escape

from ..layout import LayoutElement
from .renderer_base import LayoutRenderer


class DrawioRenderer(LayoutRenderer):
    renderer_name = "drawio"
    GRID_TO_PX = 40

    def render(self) -> str:
        nodes = self._collect_nodes()
        edges = self._collect_edges(nodes)

        id_map = {id(node): f"n_{idx}" for idx, node in enumerate(nodes, start=2)}
        next_edge_id = len(nodes) + 2

        lines = [
            '<mxfile host="app.diagrams.net" modified="2026-03-05T00:00:00.000Z" agent="anansi" version="24.7.17">',
            '  <diagram id="anansi" name="Page-1">',
            '    <mxGraphModel dx="1200" dy="800" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1920" pageHeight="1080" math="0" shadow="0">',
            "      <root>",
            '        <mxCell id="0" />',
            '        <mxCell id="1" parent="0" />',
        ]

        for node in nodes:
            node_id = id_map[id(node)]
            label = escape(str(node.entity) if node.entity else "root")
            x = int(node.x or 0) * self.GRID_TO_PX
            y = int(node.y or 0) * self.GRID_TO_PX
            w = max(20, int(node.w or 0) * self.GRID_TO_PX)
            h = max(20, int(node.h or 0) * self.GRID_TO_PX)
            lines.append(
                f'        <mxCell id="{node_id}" value="{label}" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#eaf2ff;strokeColor=#557aa6;" vertex="1" parent="1">'
            )
            lines.append(
                f'          <mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry" />'
            )
            lines.append("        </mxCell>")

        for src, dst in edges:
            edge_id = f"e_{next_edge_id}"
            next_edge_id += 1
            lines.append(
                f'        <mxCell id="{edge_id}" style="endArrow=block;html=1;rounded=0;" edge="1" source="{id_map[id(src)]}" target="{id_map[id(dst)]}" parent="1">'
            )
            lines.append('          <mxGeometry relative="1" as="geometry" />')
            lines.append("        </mxCell>")

        lines.extend(
            [
                "      </root>",
                "    </mxGraphModel>",
                "  </diagram>",
                "</mxfile>",
            ]
        )
        return "\n".join(lines)

    def _collect_nodes(self) -> list[LayoutElement]:
        nodes = []
        stack = [self.layout.root]
        while stack:
            node = stack.pop()
            if not node.is_root:
                nodes.append(node)
            stack.extend(node.deploy_children.values())
        return nodes

    def _collect_edges(
        self, nodes: list[LayoutElement]
    ) -> list[tuple[LayoutElement, LayoutElement]]:
        by_id = {id(node): node for node in nodes}
        use_real_edges = any(node.real_data_stream_children for node in nodes)
        unique = set()
        result = []
        for node in nodes:
            stream_children = (
                node.real_data_stream_children
                if use_real_edges
                else node.data_stream_children
            )
            for child in stream_children.values():
                src_id = id(node)
                dst_id = id(child)
                if src_id not in by_id or dst_id not in by_id:
                    continue
                key = (src_id, dst_id)
                if key in unique:
                    continue
                unique.add(key)
                result.append((by_id[src_id], by_id[dst_id]))
        return result
