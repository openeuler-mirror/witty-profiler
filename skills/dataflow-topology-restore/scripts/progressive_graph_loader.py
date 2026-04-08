"""
Progressive Graph Loader

本脚本提供渐进式加载功能，支持按需加载 Graph 数据，避免全量加载导致上下文溢出。
不包含分析逻辑，仅提供数据访问接口。

Usage:
    from progressive_graph_loader import GraphLoader
    
    loader = GraphLoader("path/to/graph.json")
    
    # 渐进式加载示例
    summary = loader.load_summary()  # 第一步：加载摘要
    memory_data = loader.load_memory_related_data()  # 第二步：加载内存相关数据
"""

import json
from typing import Dict, List, Any, Optional, Set
from pathlib import Path


class GraphLoader:
    """渐进式 Graph 加载器"""
    
    def __init__(self, file_path: str):
        """
        初始化加载器
        
        Args:
            file_path: Graph JSON 文件路径
        """
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"Graph file not found: {file_path}")
        
        self._file_handle = None
        self._index_cache = {}
    
    def load_summary(self) -> Dict[str, Any]:
        """
        加载 Graph 摘要信息（不加载具体数据）
        
        Returns:
            摘要信息字典
        """
        with open(self.file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        nodes = data.get('nodes', [])
        edges = data.get('edges', [])
        
        entity_types = {}
        for node in nodes:
            et = node.get('entity_type', 'Unknown')
            entity_types[et] = entity_types.get(et, 0) + 1
        
        edge_types = {}
        for edge in edges:
            et = edge.get('edge_type', 'Unknown')
            edge_types[et] = edge_types.get(et, 0) + 1
        
        return {
            'total_nodes': len(nodes),
            'total_edges': len(edges),
            'entity_types': entity_types,
            'edge_types': edge_types,
            'file_size_mb': self.file_path.stat().st_size / (1024 * 1024)
        }
    
    def load_entities_by_type(self, entity_types: List[str]) -> List[Dict[str, Any]]:
        """
        按类型加载实体
        
        Args:
            entity_types: 实体类型列表
            
        Returns:
            匹配的实体列表
        """
        with open(self.file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        nodes = data.get('nodes', [])
        return [node for node in nodes if node.get('entity_type') in entity_types]
    
    def load_edges_by_type(self, edge_types: List[str]) -> List[Dict[str, Any]]:
        """
        按类型加载边
        
        Args:
            edge_types: 边类型列表
            
        Returns:
            匹配的边列表
        """
        with open(self.file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        edges = data.get('edges', [])
        return [edge for edge in edges if edge.get('edge_type') in edge_types]
    
    def load_memory_related_data(self) -> Dict[str, Any]:
        """
        加载内存相关的实体和边
        
        Returns:
            内存相关数据
        """
        memory_entity_types = [
            'NumaEntity', 'NumaSetEntity', 'ProcessEntity', 'ThreadEntity'
        ]
        
        memory_edge_types = [
            'NumaAccessEdge', 'AffinitativeToNuma', 'NumaSetContainEdge'
        ]
        
        entities = self.load_entities_by_type(memory_entity_types)
        edges = self.load_edges_by_type(memory_edge_types)
        
        return {
            'entities': entities,
            'edges': edges,
            'summary': {
                'entity_count': len(entities),
                'edge_count': len(edges)
            }
        }
    
    def load_compute_related_data(self) -> Dict[str, Any]:
        """
        加载计算相关的实体和边
        
        Returns:
            计算相关数据
        """
        compute_entity_types = [
            'ProcessEntity', 'ThreadEntity', 'NPUEntity', 'GPUEntity'
        ]
        
        compute_edge_types = [
            'AccessEdge', 'OwnEdge', 'BelongEdge'
        ]
        
        entities = self.load_entities_by_type(compute_entity_types)
        edges = self.load_edges_by_type(compute_edge_types)
        
        return {
            'entities': entities,
            'edges': edges,
            'summary': {
                'entity_count': len(entities),
                'edge_count': len(edges)
            }
        }
    
    def load_communication_related_data(self) -> Dict[str, Any]:
        """
        加载通信相关的实体和边
        
        Returns:
            通信相关数据
        """
        comm_entity_types = [
            'ProcessEntity', 'ThreadEntity', 'SocketEntity', 'SharedMemoryEntity'
        ]
        
        comm_edge_types = [
            'SendToSocketEdge', 'ConnectToEdge', 'IPCEdge', 'BelongEdge'
        ]
        
        entities = self.load_entities_by_type(comm_entity_types)
        edges = self.load_edges_by_type(comm_edge_types)
        
        return {
            'entities': entities,
            'edges': edges,
            'summary': {
                'entity_count': len(entities),
                'edge_count': len(edges)
            }
        }
    
    def load_io_related_data(self) -> Dict[str, Any]:
        """
        加载 I/O 相关的实体和边
        
        Returns:
            I/O 相关数据
        """
        io_entity_types = [
            'ProcessEntity', 'ThreadEntity'
        ]
        
        io_edge_types = [
            'AccessEdge', 'SendToSocketEdge'
        ]
        
        entities = self.load_entities_by_type(io_entity_types)
        edges = self.load_edges_by_type(io_edge_types)
        
        return {
            'entities': entities,
            'edges': edges,
            'summary': {
                'entity_count': len(entities),
                'edge_count': len(edges)
            }
        }
    
    def load_hotspot_thread_data(self) -> Dict[str, Any]:
        """
        加载热点线程分析所需的数据
        
        Returns:
            热点线程相关数据
        """
        entity_types = [
            'ThreadEntity', 'ProcessEntity'
        ]
        
        edge_types = [
            'OwnEdge', 'BelongEdge', 'NumaAccessEdge'
        ]
        
        entities = self.load_entities_by_type(entity_types)
        edges = self.load_edges_by_type(edge_types)
        
        return {
            'entities': entities,
            'edges': edges,
            'summary': {
                'entity_count': len(entities),
                'edge_count': len(edges)
            }
        }
    
    def load_dataflow_topology_data(self) -> Dict[str, Any]:
        """
        加载数据流拓扑分析所需的数据
        
        Returns:
            数据流拓扑相关数据
        """
        entity_types = [
            'ProcessEntity', 'ThreadEntity', 'NPUEntity', 'GPUEntity',
            'NumaEntity', 'NumaSetEntity', 'SocketEntity', 'SharedMemoryEntity'
        ]
        
        edge_types = [
            'AccessEdge', 'NumaAccessEdge', 'SendToSocketEdge', 
            'ConnectToEdge', 'AffinitativeToNuma', 'OwnEdge', 'BelongEdge'
        ]
        
        entities = self.load_entities_by_type(entity_types)
        edges = self.load_edges_by_type(edge_types)
        
        return {
            'entities': entities,
            'edges': edges,
            'summary': {
                'entity_count': len(entities),
                'edge_count': len(edges)
            }
        }
    
    def load_bottleneck_layer_data(self, layer: str) -> Dict[str, Any]:
        """
        加载特定瓶颈层次的数据
        
        Args:
            layer: 瓶颈层次（compute/memory/interconnect/network/storage/control_plane/data_plane）
            
        Returns:
            特定层次的数据
        """
        layer_mapping = {
            'compute': self.load_compute_related_data,
            'memory': self.load_memory_related_data,
            'interconnect': self.load_memory_related_data,
            'network': self.load_communication_related_data,
            'storage': self.load_io_related_data,
            'control_plane': self.load_communication_related_data,
            'data_plane': self.load_io_related_data
        }
        
        loader_func = layer_mapping.get(layer)
        if not loader_func:
            raise ValueError(f"Unknown bottleneck layer: {layer}")
        
        return loader_func()
    
    def load_entities_by_ids(self, global_ids: List[str]) -> List[Dict[str, Any]]:
        """
        按全局 ID 加载实体
        
        Args:
            global_ids: 全局 ID 列表
            
        Returns:
            匹配的实体列表
        """
        with open(self.file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        nodes = data.get('nodes', [])
        return [node for node in nodes if self._compute_global_id(node) in global_ids]
    
    def _compute_global_id(self, entity: Dict[str, Any]) -> str:
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


def print_summary(summary: Dict[str, Any]) -> None:
    """
    打印摘要信息
    
    Args:
        summary: 摘要数据
    """
    print("=" * 60)
    print("Anansi Graph Summary")
    print("=" * 60)
    print(f"Total Nodes: {summary['total_nodes']}")
    print(f"Total Edges: {summary['total_edges']}")
    print(f"File Size: {summary['file_size_mb']:.2f} MB")
    print()
    print("Entity Types:")
    for et, count in sorted(summary['entity_types'].items()):
        print(f"  {et}: {count}")
    print()
    print("Edge Types:")
    for et, count in sorted(summary['edge_types'].items()):
        print(f"  {et}: {count}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python progressive_graph_loader.py <graph.json>")
        sys.exit(1)
    
    graph_file = sys.argv[1]
    loader = GraphLoader(graph_file)
    
    print("Loading summary...")
    summary = loader.load_summary()
    print_summary(summary)
    
    print("\n" + "=" * 60)
    print("Progressive Loading Example")
    print("=" * 60)
    
    print("\nLoading memory-related data...")
    memory_data = loader.load_memory_related_data()
    print(f"Memory entities: {memory_data['summary']['entity_count']}")
    print(f"Memory edges: {memory_data['summary']['edge_count']}")
    
    print("\nLoading compute-related data...")
    compute_data = loader.load_compute_related_data()
    print(f"Compute entities: {compute_data['summary']['entity_count']}")
    print(f"Compute edges: {compute_data['summary']['edge_count']}")
