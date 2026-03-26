import numpy as np


class Gridifier:
    """
    Convert the x,y positions into grids
    """

    @staticmethod
    def gridify_with_conflict_resolution(
        pos: dict[int, tuple[float, float]], grid_size=1.0
    ):
        # 初始：四舍五入到最近网格点
        raw_grid = {
            node: (int(round(x / grid_size)), int(round(y / grid_size)))
            for node, (x, y) in pos.items()
        }

        # 检测冲突并分散
        from collections import defaultdict

        cell_to_nodes = defaultdict(list)
        for node, cell in raw_grid.items():
            cell_to_nodes[cell].append(node)

        final_grid = {}
        for cell, nodes in cell_to_nodes.items():
            if len(nodes) == 1:
                final_grid[nodes[0]] = cell
            else:
                # 在 cell 周围找空位（简单螺旋搜索）
                cx, cy = cell
                occupied = set(final_grid.values())
                for r in range(1, 20):  # 最大搜索半径
                    found = 0
                    for dx in range(-r, r + 1):
                        for dy in range(-r, r + 1):
                            if max(abs(dx), abs(dy)) != r:
                                continue
                            candidate = (cx + dx, cy + dy)
                            if candidate not in occupied:
                                if found < len(nodes):
                                    final_grid[nodes[found]] = candidate
                                    occupied.add(candidate)
                                    found += 1
                            if found == len(nodes):
                                break
                        if found == len(nodes):
                            break
                    if found == len(nodes):
                        break
        return final_grid

    @staticmethod
    def gridify_naive(pos: dict[int, tuple[float, float]]):
        nodes = list(pos.keys())

        # 获取排序后的唯一顺序（处理相等情况）
        sorted_x_nodes = sorted(nodes, key=lambda n: pos[n][0])
        sorted_y_nodes = sorted(nodes, key=lambda n: pos[n][1])

        # 构建 rank 映射（这里强制唯一）
        x_rank = {node: i for i, node in enumerate(sorted_x_nodes)}
        y_rank = {node: i for i, node in enumerate(sorted_y_nodes)}

        grid_pos = {node: (x_rank[node], y_rank[node]) for node in nodes}
        return grid_pos
