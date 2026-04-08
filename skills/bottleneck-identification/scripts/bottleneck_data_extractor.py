"""
Bottleneck Data Extractor

本脚本负责从 Anansi Graph 和监控数据中提取瓶颈分析所需的原始数据。
不包含分析逻辑，仅提供数据提取和格式化接口。

Usage:
    from bottleneck_data_extractor import BottleneckDataExtractor
    
    extractor = BottleneckDataExtractor("path/to/graph.json")
    compute_data = extractor.extract_compute_layer_data()
    memory_data = extractor.extract_memory_layer_data()
"""

import json
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime


class BottleneckDataExtractor:
    """瓶颈分析数据提取器"""
    
    def __init__(self, graph_path: str):
        """
        初始化数据提取器
        
        Args:
            graph_path: Anansi Graph JSON 文件路径
        """
        self.graph_path = Path(graph_path)
        if not self.graph_path.exists():
            raise FileNotFoundError(f"Graph file not found: {graph_path}")
        
        self._graph_data = None
    
    def _load_graph(self) -> Dict[str, Any]:
        """加载 Graph 数据"""
        if self._graph_data is None:
            with open(self.graph_path, 'r', encoding='utf-8') as f:
                self._graph_data = json.load(f)
        return self._graph_data
    
    def extract_summary(self) -> Dict[str, Any]:
        """
        提取系统摘要信息
        
        Returns:
            系统摘要数据
        """
        graph = self._load_graph()
        nodes = graph.get('nodes', [])
        edges = graph.get('edges', [])
        
        entity_counts = {}
        for node in nodes:
            et = node.get('entity_type', 'Unknown')
            entity_counts[et] = entity_counts.get(et, 0) + 1
        
        edge_counts = {}
        for edge in edges:
            et = edge.get('edge_type', 'Unknown')
            edge_counts[et] = edge_counts.get(et, 0) + 1
        
        return {
            'total_nodes': len(nodes),
            'total_edges': len(edges),
            'entity_counts': entity_counts,
            'edge_counts': edge_counts,
            'file_size_mb': self.graph_path.stat().st_size / (1024 * 1024),
            'extraction_time': datetime.now().isoformat()
        }
    
    def extract_compute_layer_data(self) -> Dict[str, Any]:
        """
        提取计算层数据
        
        Returns:
            计算层相关数据
        """
        graph = self._load_graph()
        nodes = graph.get('nodes', [])
        edges = graph.get('edges', [])
        
        compute_entity_types = ['ProcessEntity', 'ThreadEntity', 'NPUEntity', 'GPUEntity']
        compute_edge_types = ['AccessEdge', 'OwnEdge', 'BelongEdge']
        
        entities = [n for n in nodes if n.get('entity_type') in compute_entity_types]
        filtered_edges = [e for e in edges if e.get('edge_type') in compute_edge_types]
        
        return {
            'entities': entities,
            'edges': filtered_edges,
            'summary': {
                'entity_count': len(entities),
                'edge_count': len(filtered_edges)
            }
        }
    
    def extract_memory_layer_data(self) -> Dict[str, Any]:
        """
        提取内存层数据
        
        Returns:
            内存层相关数据
        """
        graph = self._load_graph()
        nodes = graph.get('nodes', [])
        edges = graph.get('edges', [])
        
        memory_entity_types = ['NumaEntity', 'NumaSetEntity', 'ProcessEntity', 'ThreadEntity']
        memory_edge_types = ['NumaAccessEdge', 'AffinitativeToNuma', 'NumaSetContainEdge']
        
        entities = [n for n in nodes if n.get('entity_type') in memory_entity_types]
        filtered_edges = [e for e in edges if e.get('edge_type') in memory_edge_types]
        
        numa_access_data = []
        for edge in filtered_edges:
            if edge.get('edge_type') == 'NumaAccessEdge':
                numa_access_data.append(self._extract_numa_access_info(edge))
        
        return {
            'entities': entities,
            'edges': filtered_edges,
            'numa_access_data': numa_access_data,
            'summary': {
                'entity_count': len(entities),
                'edge_count': len(filtered_edges),
                'numa_access_count': len(numa_access_data)
            }
        }
    
    def extract_interconnect_layer_data(self) -> Dict[str, Any]:
        """
        提取互连层数据
        
        Returns:
            互连层相关数据
        """
        graph = self._load_graph()
        nodes = graph.get('nodes', [])
        edges = graph.get('edges', [])
        
        interconnect_entity_types = ['NumaEntity', 'NPUEntity', 'GPUEntity']
        interconnect_edge_types = ['AffinitativeToNuma', 'HCCSEdge']
        
        entities = [n for n in nodes if n.get('entity_type') in interconnect_entity_types]
        filtered_edges = [e for e in edges if e.get('edge_type') in interconnect_edge_types]
        
        return {
            'entities': entities,
            'edges': filtered_edges,
            'summary': {
                'entity_count': len(entities),
                'edge_count': len(filtered_edges)
            }
        }
    
    def extract_network_layer_data(self) -> Dict[str, Any]:
        """
        提取网络层数据
        
        Returns:
            网络层相关数据
        """
        graph = self._load_graph()
        nodes = graph.get('nodes', [])
        edges = graph.get('edges', [])
        
        network_entity_types = ['ProcessEntity', 'ThreadEntity', 'SocketEntity']
        network_edge_types = ['SendToSocketEdge', 'ConnectToEdge', 'SocketEdge']
        
        entities = [n for n in nodes if n.get('entity_type') in network_entity_types]
        filtered_edges = [e for e in edges if e.get('edge_type') in network_edge_types]
        
        socket_traffic = []
        for edge in filtered_edges:
            if edge.get('edge_type') in ['SendToSocketEdge', 'SocketEdge']:
                socket_traffic.append(self._extract_socket_traffic_info(edge))
        
        return {
            'entities': entities,
            'edges': filtered_edges,
            'socket_traffic': socket_traffic,
            'summary': {
                'entity_count': len(entities),
                'edge_count': len(filtered_edges),
                'traffic_count': len(socket_traffic)
            }
        }
    
    def extract_storage_layer_data(self) -> Dict[str, Any]:
        """
        提取存储层数据
        
        Returns:
            存储层相关数据
        """
        graph = self._load_graph()
        nodes = graph.get('nodes', [])
        edges = graph.get('edges', [])
        
        storage_entity_types = ['ProcessEntity', 'ThreadEntity']
        storage_edge_types = ['AccessEdge']
        
        entities = [n for n in nodes if n.get('entity_type') in storage_entity_types]
        filtered_edges = [e for e in edges if e.get('edge_type') in storage_edge_types]
        
        return {
            'entities': entities,
            'edges': filtered_edges,
            'summary': {
                'entity_count': len(entities),
                'edge_count': len(filtered_edges)
            }
        }
    
    def extract_ipc_layer_data(self) -> Dict[str, Any]:
        """
        提取IPC层数据
        
        Returns:
            IPC层相关数据
        """
        graph = self._load_graph()
        nodes = graph.get('nodes', [])
        edges = graph.get('edges', [])
        
        ipc_entity_types = ['ProcessEntity', 'ThreadEntity', 'SharedMemoryEntity']
        ipc_edge_types = ['IPCEdge', 'PipeEdge', 'PosixMQEdge', 'SysVMsgEdge', 'SysVSemEdge']
        
        entities = [n for n in nodes if n.get('entity_type') in ipc_entity_types]
        filtered_edges = [e for e in edges if e.get('edge_type') in ipc_edge_types]
        
        return {
            'entities': entities,
            'edges': filtered_edges,
            'summary': {
                'entity_count': len(entities),
                'edge_count': len(filtered_edges)
            }
        }
    
    def extract_all_layers_data(self) -> Dict[str, Any]:
        """
        提取所有瓶颈层数据
        
        Returns:
            所有层次的数据
        """
        return {
            'summary': self.extract_summary(),
            'compute': self.extract_compute_layer_data(),
            'memory': self.extract_memory_layer_data(),
            'interconnect': self.extract_interconnect_layer_data(),
            'network': self.extract_network_layer_data(),
            'storage': self.extract_storage_layer_data(),
            'ipc': self.extract_ipc_layer_data()
        }
    
    def _extract_numa_access_info(self, numa_edge: Dict[str, Any]) -> Dict[str, Any]:
        """
        提取NUMA访问信息
        
        Args:
            numa_edge: NumaAccessEdge 数据
            
        Returns:
            NUMA访问原始数据
        """
        info = numa_edge.get('numa_access_info', {})
        affinity = info.get('numa_affinity_info', {})
        
        return {
            'source_entity': numa_edge.get('source_node', {}).get('entity_type'),
            'source_id': numa_edge.get('source_node', {}).get('tid') or 
                        numa_edge.get('source_node', {}).get('pid'),
            'cpu_runtime_distribution': affinity.get('cpu_runtime_pct_in_each_numa', []),
            'memory_page_distribution': affinity.get('mem_pages_in_each_numa', []),
            'cpu_mem_similarity': affinity.get('cpu_mem_access_cosine_similarity', 0),
            'total_memory_pages': affinity.get('total_dirty_anon_pages', 0)
        }
    
    def _extract_socket_traffic_info(self, socket_edge: Dict[str, Any]) -> Dict[str, Any]:
        """
        提取Socket流量信息
        
        Args:
            socket_edge: Socket相关边数据
            
        Returns:
            Socket流量原始数据
        """
        source = socket_edge.get('source_node', {})
        target = socket_edge.get('target_node', {})
        
        return {
            'source_entity': source.get('entity_type'),
            'source_id': source.get('pid') or source.get('tid'),
            'target_entity': target.get('entity_type'),
            'target_socket': f"{target.get('socket_addr')}:{target.get('socket_port')}",
            'socket_type': target.get('socket_type'),
            'edge_type': socket_edge.get('edge_type')
        }
    
    def extract_entity_metrics(self, entity_type: str, entity_id: int) -> Dict[str, Any]:
        """
        提取特定实体的性能指标
        
        Args:
            entity_type: 实体类型
            entity_id: 实体ID
            
        Returns:
            实体性能指标数据
        """
        graph = self._load_graph()
        nodes = graph.get('nodes', [])
        
        for node in nodes:
            if node.get('entity_type') == entity_type:
                if entity_type == 'ThreadEntity' and node.get('tid') == entity_id:
                    return self._extract_thread_metrics(node)
                elif entity_type == 'ProcessEntity' and node.get('pid') == entity_id:
                    return self._extract_process_metrics(node)
        
        return {}
    
    def _extract_thread_metrics(self, thread_entity: Dict[str, Any]) -> Dict[str, Any]:
        """
        提取线程性能指标
        
        Args:
            thread_entity: ThreadEntity 数据
            
        Returns:
            线程性能指标
        """
        metrics = {
            'tid': thread_entity.get('tid'),
            'name': thread_entity.get('name', 'unknown'),
            'process_pid': thread_entity.get('process_pid'),
            'cpu_affinity': thread_entity.get('cpu_affinity', [])
        }
        
        sched_data = thread_entity.get('sched_monitor', {})
        if sched_data:
            metrics['sched'] = {
                'cpu_usage_pct': sched_data.get('cpu_usage_pct', 0),
                'voluntary_ctxt_switches': sched_data.get('voluntary_ctxt_switches', 0),
                'nonvoluntary_ctxt_switches': sched_data.get('nonvoluntary_ctxt_switches', 0)
            }
        
        cache_data = thread_entity.get('cache_monitor', {})
        if cache_data:
            metrics['cache'] = {
                'l1i_miss_rate': cache_data.get('l1i_miss_rate', 0),
                'llc_miss_rate': cache_data.get('llc_miss_rate', 0)
            }
        
        return metrics
    
    def _extract_process_metrics(self, process_entity: Dict[str, Any]) -> Dict[str, Any]:
        """
        提取进程性能指标
        
        Args:
            process_entity: ProcessEntity 数据
            
        Returns:
            进程性能指标
        """
        metrics = {
            'pid': process_entity.get('pid'),
            'ppid': process_entity.get('ppid'),
            'name': process_entity.get('name', 'unknown'),
            'cmdline': process_entity.get('cmdline', ''),
            'num_threads': process_entity.get('num_threads', 0)
        }
        
        sched_data = process_entity.get('sched_monitor', {})
        if sched_data:
            metrics['sched'] = {
                'cpu_usage_pct': sched_data.get('cpu_usage_pct', 0)
            }
        
        mem_data = process_entity.get('memory_info', {})
        if mem_data:
            metrics['memory'] = {
                'rss_mb': mem_data.get('rss_mb', 0),
                'vms_mb': mem_data.get('vms_mb', 0)
            }
        
        return metrics


def format_bottleneck_data(data: Dict[str, Any], output_format: str = 'dict') -> Any:
    """
    格式化瓶颈数据
    
    Args:
        data: 瓶颈数据
        output_format: 输出格式 ('dict', 'json', 'summary')
        
    Returns:
        格式化后的数据
    """
    if output_format == 'json':
        return json.dumps(data, indent=2, ensure_ascii=False)
    elif output_format == 'summary':
        lines = []
        lines.append("=" * 60)
        lines.append("Bottleneck Data Summary")
        lines.append("=" * 60)
        
        if 'summary' in data:
            summary = data['summary']
            lines.append(f"Total Nodes: {summary.get('total_nodes', 0)}")
            lines.append(f"Total Edges: {summary.get('total_edges', 0)}")
            lines.append(f"File Size: {summary.get('file_size_mb', 0):.2f} MB")
        
        for layer in ['compute', 'memory', 'interconnect', 'network', 'storage', 'ipc']:
            if layer in data:
                layer_data = data[layer]
                summary = layer_data.get('summary', {})
                lines.append(f"\n{layer.upper()} Layer:")
                lines.append(f"  Entities: {summary.get('entity_count', 0)}")
                lines.append(f"  Edges: {summary.get('edge_count', 0)}")
        
        return '\n'.join(lines)
    else:
        return data


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python bottleneck_data_extractor.py <graph.json>")
        sys.exit(1)
    
    graph_file = sys.argv[1]
    extractor = BottleneckDataExtractor(graph_file)
    
    print("Extracting all layers data...")
    all_data = extractor.extract_all_layers_data()
    
    print(format_bottleneck_data(all_data, output_format='summary'))
