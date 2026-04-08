"""
Anansi Graph 解析工具

本脚本负责加载 JSON 格式的 Anansi Graph 文件，提取 Entity 和 Edge 列表
不包含分析逻辑，仅提供数据访问接口

Usage:
    from parse_anansi_graph import load_graph, get_entities_by_type, get_edges_by_type
    
    graph = load_graph("path/to/graph.json")
    processes = get_entities_by_type(graph, "ProcessEntity")
    npu_access_edges = get_edges_by_type(graph, "AccessEdge")
"""

import json
from typing import Dict, List, Any, Optional
from pathlib import Path


def load_graph(file_path: str) -> Dict[str, Any]:
    """
    加载 Anansi Graph JSON 文件
    
    Args:
        file_path: Graph JSON 文件路径
        
    Returns:
        包含 'nodes' 和 'edges' 的字典
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Graph file not found: {file_path}")
    
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if 'nodes' not in data or 'edges' not in data:
        raise ValueError("Invalid graph format: missing 'nodes' or 'edges' key")
    
    return data


def get_entities_by_type(graph: Dict[str, Any], entity_type: str) -> List[Dict[str, Any]]:
    """
    按类型获取实体列表
    
    Args:
        graph: Graph 数据
        entity_type: 实体类型名称
        
    Returns:
        匹配的实体列表
    """
    return [node for node in graph.get('nodes', []) 
            if node.get('entity_type') == entity_type]


def get_edges_by_type(graph: Dict[str, Any], edge_type: str) -> List[Dict[str, Any]]:
    """
    按类型获取边列表
    
    Args:
        graph: Graph 数据
        edge_type: 边类型名称
        
    Returns:
        匹配的边列表
    """
    return [edge for edge in graph.get('edges', []) 
            if edge.get('edge_type') == edge_type]


def get_entity_by_global_id(graph: Dict[str, Any], global_id: str) -> Optional[Dict[str, Any]]:
    """
    通过 global_id 获取实体
    
    Args:
        graph: Graph 数据
        global_id: 实体的全局 ID
        
    Returns:
        匹配的实体，如果未找到返回 None
    """
    for node in graph.get('nodes', []):
        if compute_global_id(node) == global_id:
            return node
    return None


def compute_global_id(entity: Dict[str, Any]) -> str:
    """
    计算实体的 global_id
    
    Args:
        entity: 实体数据
        
    Returns:
        global_id 字符串
    """
    entity_type = entity.get('entity_type', '')
    
    if entity_type == 'ProcessEntity':
        return f"Process(pid={entity.get('pid')},ppid={entity.get('ppid')})"
    elif entity_type == 'ThreadEntity':
        return f"Thread(tid={entity.get('tid')})"
    elif entity_type == 'NPUEntity':
        return f"NPU(id={entity.get('id')},cpu_affinity={entity.get('cpu_affinity')})"
    elif entity_type == 'GPUEntity':
        return f"GPU(id={entity.get('id')},pci_bus_id={entity.get('pci_bus_id')})"
    elif entity_type == 'NumaEntity':
        return f"numa{entity.get('numa_id')}"
    elif entity_type == 'NumaSetEntity':
        return f"{{{entity.get('numa_id_str')}}}"
    elif entity_type == 'SocketEntity':
        return f"{entity.get('socket_addr')}:{entity.get('socket_port')}({entity.get('socket_type')})"
    elif entity_type == 'ContainerEntity':
        return entity.get('container_id', 'unknown')
    elif entity_type == 'SharedMemoryEntity':
        return f"name={entity.get('shm_name')},size={entity.get('shm_size')}"
    else:
        return f"{entity_type}({entity.get('unique_id', 'unknown')})"


def get_process_tree(graph: Dict[str, Any]) -> Dict[int, List[int]]:
    """
    构建进程树结构
    
    Args:
        graph: Graph 数据
        
    Returns:
        进程树字典 {parent_pid: [child_pids]}
    """
    processes = get_entities_by_type(graph, 'ProcessEntity')
    tree: Dict[int, List[int]] = {}
    
    for proc in processes:
        pid = proc.get('pid')
        ppid = proc.get('ppid')
        
        if ppid not in tree:
            tree[ppid] = []
        if pid not in tree:
            tree[pid] = []
        
        if pid and ppid:
            tree[ppid].append(pid)
    
    return tree


def get_npu_numa_mapping(graph: Dict[str, Any]) -> Dict[int, int]:
    """
    获取 NPU 到 NUMA 的映射关系
    
    Args:
        graph: Graph 数据
        
    Returns:
        NPU ID 到 NUMA ID 的映射字典
    """
    mapping = {}
    
    affinity_edges = get_edges_by_type(graph, 'AffinitativeToNuma')
    for edge in affinity_edges:
        source = edge.get('source_node', {})
        target = edge.get('target_node', {})
        
        if source.get('entity_type') == 'NPUEntity':
            npu_id = source.get('id')
            numa_id_str = target.get('numa_id_str', '')
            
            try:
                numa_id = int(numa_id_str.split(',')[0])
                mapping[npu_id] = numa_id
            except (ValueError, IndexError):
                pass
    
    return mapping


def get_process_npu_access(graph: Dict[str, Any]) -> Dict[int, List[int]]:
    """
    获取进程到 NPU 的访问关系
    
    Args:
        graph: Graph 数据
        
    Returns:
        进程 PID 到 NPU ID 列表的映射字典
    """
    mapping: Dict[int, List[int]] = {}
    
    access_edges = get_edges_by_type(graph, 'AccessEdge')
    for edge in access_edges:
        source = edge.get('source_node', {})
        target = edge.get('target_node', {})
        
        if source.get('entity_type') == 'ProcessEntity':
            pid = source.get('pid')
            if target.get('entity_type') == 'NPUEntity':
                npu_id = target.get('id')
                if pid not in mapping:
                    mapping[pid] = []
                mapping[pid].append(npu_id)
    
    return mapping


def get_numa_access_data(numa_access_edge: Dict[str, Any]) -> Dict[str, Any]:
    """
    提取 NUMA 访问数据（不包含分析逻辑）
    
    Args:
        numa_access_edge: NumaAccessEdge 数据
        
    Returns:
        NUMA 访问原始数据
    """
    info = numa_access_edge.get('numa_access_info', {})
    affinity = info.get('numa_affinity_info', {})
    
    return {
        'cpu_runtime_distribution': affinity.get('cpu_runtime_pct_in_each_numa', []),
        'memory_page_distribution': affinity.get('mem_pages_in_each_numa', []),
        'cpu_mem_similarity': affinity.get('cpu_mem_access_cosine_similarity', 0),
        'total_memory_pages': affinity.get('total_dirty_anon_pages', 0)
    }


def print_graph_summary(graph: Dict[str, Any]) -> None:
    """
    打印 Graph 摘要信息
    
    Args:
        graph: Graph 数据
    """
    nodes = graph.get('nodes', [])
    edges = graph.get('edges', [])
    
    entity_types = {}
    for node in nodes:
        et = node.get('entity_type', 'Unknown')
        entity_types[et] = entity_types.get(et, 0) + 1
    
    edge_types = {}
    for edge in edges:
        et = edge.get('edge_type', 'Unknown')
        edge_types[et] = edge_types.get(et, 0) + 1
    
    print("=" * 60)
    print("Anansi Graph Summary")
    print("=" * 60)
    print(f"Total Nodes: {len(nodes)}")
    print(f"Total Edges: {len(edges)}")
    print()
    print("Entity Types:")
    for et, count in sorted(entity_types.items()):
        print(f"  {et}: {count}")
    print()
    print("Edge Types:")
    for et, count in sorted(edge_types.items()):
        print(f"  {et}: {count}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python parse-anansi-graph.py <graph.json>")
        sys.exit(1)
    
    graph_file = sys.argv[1]
    graph = load_graph(graph_file)
    print_graph_summary(graph)
