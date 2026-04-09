"""
Progressive Graph Loader for Hotspot Thread Discovery

本脚本提供渐进式加载功能，专门用于热点线程分析，避免全量加载导致上下文溢出。
不包含分析逻辑，仅提供数据访问接口。

Usage:
    from progressive_loader import GraphLoader
    
    loader = GraphLoader("path/to/graph.json")
    
    # 渐进式加载示例
    summary = loader.load_summary()  # 第一步：加载摘要
    hotspot_data = loader.load_hotspot_thread_data()  # 第二步：加载热点线程数据
"""

import json
from typing import Dict, List, Any, Optional
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
    
    def load_hotspot_thread_data(self) -> Dict[str, Any]:
        """
        加载热点线程分析所需的数据
        
        Returns:
            热点线程相关数据
        """
        with open(self.file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        nodes = data.get('nodes', [])
        edges = data.get('edges', [])
        
        entity_types = ['ThreadEntity', 'ProcessEntity']
        edge_types = ['OwnEdge', 'BelongEdge', 'NumaAccessEdge']
        
        entities = [n for n in nodes if n.get('entity_type') in entity_types]
        filtered_edges = [e for e in edges if e.get('edge_type') in edge_types]
        
        return {
            'entities': entities,
            'edges': filtered_edges,
            'summary': {
                'entity_count': len(entities),
                'edge_count': len(filtered_edges)
            }
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
        print("Usage: python progressive_loader.py <graph.json>")
        sys.exit(1)
    
    graph_file = sys.argv[1]
    loader = GraphLoader(graph_file)
    
    print("Loading summary...")
    summary = loader.load_summary()
    print_summary(summary)
    
    print("\n" + "=" * 60)
    print("Progressive Loading Example")
    print("=" * 60)
    
    print("\nLoading hotspot thread data...")
    hotspot_data = loader.load_hotspot_thread_data()
    print(f"Hotspot entities: {hotspot_data['summary']['entity_count']}")
    print(f"Hotspot edges: {hotspot_data['summary']['edge_count']}")
