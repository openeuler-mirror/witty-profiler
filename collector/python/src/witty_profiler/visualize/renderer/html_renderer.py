import html

from witty_profiler.entity.node_entity import SocketEntity

from ..layout import LayoutElement
from .renderer_base import LayoutRenderer


class HtmlRenderer(LayoutRenderer):
    renderer_name = "html"
    GRID_TO_PX = 40
    CANVAS_PADDING = 40

    def render(self) -> str:
        nodes = self._collect_nodes()
        edges = self._collect_edges()
        node_dom_ids = {id(node): f"node-{idx}" for idx, node in enumerate(nodes)}

        width = max(
            self.CANVAS_PADDING * 2,
            (int(self.layout.root.w or 0) * self.GRID_TO_PX) + self.CANVAS_PADDING * 2,
        )
        height = max(
            self.CANVAS_PADDING * 2,
            (int(self.layout.root.h or 0) * self.GRID_TO_PX) + self.CANVAS_PADDING * 2,
        )

        lines = [
            "<!DOCTYPE html>",
            '<html lang="en">',
            "<head>",
            '  <meta charset="UTF-8" />',
            '  <meta name="viewport" content="width=device-width, initial-scale=1.0" />',
            "  <title>Witty Profiler Layout</title>",
            "  <style>",
            "    body { margin: 0; font-family: 'Segoe UI', sans-serif; background: #f4f6f8; }",
            "    .wrap { padding: 16px; overflow: auto; }",
            "    .canvas { background: #ffffff; border: 1px solid #d5dbe3; border-radius: 8px; }",
            "    .node { fill: #eaf2ff; stroke: #557aa6; stroke-width: 1.5; }",
            "    .socket-node { fill: #ffe7c2; stroke: #d97800; stroke-width: 1.5; }",
            "    .node-text { font-size: 11px; fill: #1b2733; pointer-events: none; }",
            "    .edge { stroke: #7d8ea3; stroke-width: 1.2; fill: none; cursor: pointer; transition: stroke 120ms ease, stroke-width 120ms ease; }",
            "    .edge:hover, .edge.active { stroke: #ff6a00; stroke-width: 3; }",
            "    .node-group.active .node { stroke: #ff6a00; stroke-width: 2.5; fill: #fff2e8; }",
            "    .node-group.active .node-text { fill: #b34700; font-weight: 600; }",
            "  </style>",
            "</head>",
            "<body>",
            '  <div class="wrap">',
            f'    <svg class="canvas" width="{width}" height="{height}">',
            '      <g id="nodes">',
        ]

        for node in nodes:
            x = self.CANVAS_PADDING + int(node.x or 0) * self.GRID_TO_PX
            y = self.CANVAS_PADDING + int(node.y or 0) * self.GRID_TO_PX
            w = max(20, int(node.w or 0) * self.GRID_TO_PX)
            h = max(20, int(node.h or 0) * self.GRID_TO_PX)
            label = html.escape(str(node.entity) if node.entity else "root")
            node_dom_id = node_dom_ids[id(node)]

            node_depth = int(node.depth or 0)
            lines.append(
                f'      <g id="{node_dom_id}" class="node-group" data-depth="{node_depth}">'
            )
            if node.entity is not None and isinstance(node.entity, SocketEntity):
                radius = max(4, min(w, h) // 3)
                cx = x + w // 2
                cy = y + h // 2
                lines.append(
                    f'      <circle class="node socket-node" cx="{cx}" cy="{cy}" r="{radius}" />'
                )
                lines.append(
                    f'      <text class="node-text" x="{x + 8}" y="{y + 16}">Socket</text>'
                )
            else:
                lines.append(
                    f'      <rect class="node" x="{x}" y="{y}" width="{w}" height="{h}" rx="6" ry="6" />'
                )
                lines.append(
                    f'      <text class="node-text" x="{x + 8}" y="{y + 16}">{label}</text>'
                )
            lines.append("      </g>")

        lines.append("      </g>")
        lines.append('      <g id="edges">')
        for src, dst in edges:
            x1, y1 = self._center(src)
            x2, y2 = self._center(dst)
            src_dom_id = node_dom_ids.get(id(src), "")
            dst_dom_id = node_dom_ids.get(id(dst), "")
            lines.append(
                f'      <line class="edge" data-src="{src_dom_id}" data-dst="{dst_dom_id}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" />'
            )
        lines.append("      </g>")

        lines.extend(
            [
                "    </svg>",
                "  </div>",
                "  <script>",
                "    (function() {",
                "      const canvas = document.querySelector('.canvas');",
                "      const edges = Array.from(document.querySelectorAll('.edge'));",
                "      const nodeGroups = Array.from(document.querySelectorAll('.node-group'));",
                "      const edgesByNode = new Map();",
                "      let hoveredEdge = null;",
                "      let activeNodeId = null;",
                "      let lastPointerEvent = null;",
                "",
                "      function setNodeState(nodeId, active) {",
                "        if (!nodeId) return;",
                "        const node = document.getElementById(nodeId);",
                "        if (!node) return;",
                "        if (active) node.classList.add('active');",
                "        else node.classList.remove('active');",
                "      }",
                "",
                "      function addIncident(nodeId, edge) {",
                "        if (!nodeId) return;",
                "        if (!edgesByNode.has(nodeId)) edgesByNode.set(nodeId, []);",
                "        edgesByNode.get(nodeId).push(edge);",
                "      }",
                "",
                "      function clearActive() {",
                "        edges.forEach((edge) => edge.classList.remove('active'));",
                "        nodeGroups.forEach((node) => node.classList.remove('active'));",
                "      }",
                "",
                "      function activateEdge(edge) {",
                "        clearActive();",
                "        edge.classList.add('active');",
                "        setNodeState(edge.dataset.src, true);",
                "        setNodeState(edge.dataset.dst, true);",
                "      }",
                "",
                "      function activateNode(nodeId) {",
                "        clearActive();",
                "        setNodeState(nodeId, true);",
                "        const linkedEdges = edgesByNode.get(nodeId) || [];",
                "        linkedEdges.forEach((edge) => {",
                "          edge.classList.add('active');",
                "          const other = edge.dataset.src === nodeId ? edge.dataset.dst : edge.dataset.src;",
                "          setNodeState(other, true);",
                "        });",
                "      }",
                "",
                "      function pickNodeByHierarchyPriority(clientX, clientY) {",
                "        let winner = null;",
                "        let winnerDepth = -1;",
                "        let winnerArea = Number.POSITIVE_INFINITY;",
                "        nodeGroups.forEach((group) => {",
                "          const shape = group.querySelector('.node');",
                "          if (!shape) return;",
                "          const box = shape.getBoundingClientRect();",
                "          const inside = clientX >= box.left && clientX <= box.right && clientY >= box.top && clientY <= box.bottom;",
                "          if (!inside) return;",
                "          const depth = Number(group.dataset.depth || 0);",
                "          const area = box.width * box.height;",
                "          if (depth > winnerDepth || (depth === winnerDepth && area < winnerArea)) {",
                "            winner = group;",
                "            winnerDepth = depth;",
                "            winnerArea = area;",
                "          }",
                "        });",
                "        return winner ? winner.id : null;",
                "      }",
                "",
                "      function updateNodeHover(evt) {",
                "        if (hoveredEdge) return;",
                "        const nodeId = pickNodeByHierarchyPriority(evt.clientX, evt.clientY);",
                "        if (nodeId === activeNodeId) return;",
                "        activeNodeId = nodeId;",
                "        if (nodeId) activateNode(nodeId);",
                "        else clearActive();",
                "      }",
                "",
                "      edges.forEach((edge) => {",
                "        addIncident(edge.dataset.src, edge);",
                "        addIncident(edge.dataset.dst, edge);",
                "        edge.addEventListener('mouseenter', () => {",
                "          hoveredEdge = edge;",
                "          activeNodeId = null;",
                "          activateEdge(edge);",
                "        });",
                "        edge.addEventListener('mouseleave', () => {",
                "          if (hoveredEdge === edge) hoveredEdge = null;",
                "          if (lastPointerEvent) updateNodeHover(lastPointerEvent);",
                "          else clearActive();",
                "        });",
                "      });",
                "",
                "      if (canvas) {",
                "        canvas.addEventListener('mousemove', (evt) => {",
                "          lastPointerEvent = evt;",
                "          updateNodeHover(evt);",
                "        });",
                "        canvas.addEventListener('mouseleave', () => {",
                "          lastPointerEvent = null;",
                "          if (!hoveredEdge) {",
                "            activeNodeId = null;",
                "            clearActive();",
                "          }",
                "        });",
                "      }",
                "    })();",
                "  </script>",
                "</body>",
                "</html>",
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

    def _collect_edges(self) -> list[tuple[LayoutElement, LayoutElement]]:
        nodes = self._collect_nodes()
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
                if child.is_root:
                    continue
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

    def _center(self, node: LayoutElement) -> tuple[int, int]:
        x = self.CANVAS_PADDING + int(node.x or 0) * self.GRID_TO_PX
        y = self.CANVAS_PADDING + int(node.y or 0) * self.GRID_TO_PX
        w = max(20, int(node.w or 0) * self.GRID_TO_PX)
        h = max(20, int(node.h or 0) * self.GRID_TO_PX)
        return (x + w // 2, y + h // 2)
