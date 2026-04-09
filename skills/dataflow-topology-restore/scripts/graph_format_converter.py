"""
Graph Format Converter

将 Anansi Graph JSON 格式转换为紧凑的 TXT 格式，减少上下文使用。
支持渐进式转换，避免一次性加载整个 JSON 文件。

Usage:
    from graph_format_converter import GraphFormatConverter
    
    converter = GraphFormatConverter("path/to/graph.json")
    
    # 转换为紧凑格式
    summary_txt = converter.convert_summary()
    entities_txt = converter.convert_entities_by_type(['ProcessEntity', 'ThreadEntity'])
    edges_txt = converter.convert_edges_by_type(['NumaAccessEdge'])
"""

import json
from typing import Dict, List, Any, Optional
from pathlib import Path


class GraphFormatConverter:
    """Graph 格式转换器：JSON -> 紧凑 TXT 格式"""
    
    def __init__(self, graph_path: str):
        """
        初始化转换器
        
        Args:
            graph_path: Anansi Graph JSON 文件路径
        """
        self.graph_path = Path(graph_path)
        if not self.graph_path.exists():
            raise FileNotFoundError(f"Graph file not found: {graph_path}")
        
        self._graph_data = None
    
    def _load_graph(self) -> Dict[str, Any]:
        """加载 Graph 数据（延迟加载）"""
        if self._graph_data is None:
            with open(self.graph_path, 'r', encoding='utf-8') as f:
                self._graph_data = json.load(f)
        return self._graph_data
    
    def convert_summary(self) -> str:
        """
        转换摘要信息为紧凑格式
        
        Returns:
            紧凑格式的摘要字符串
        """
        graph = self._load_graph()
        nodes = graph.get('nodes', [])
        edges = graph.get('edges', [])
        
        lines = []
        lines.append(f"Graph with {len(nodes)} nodes and {len(edges)} edges")
        
        return '\n'.join(lines)
    
    def convert_entities_by_type(self, entity_types: List[str], 
                                   include_details: bool = False) -> str:
        """
        按类型转换实体为紧凑格式
        
        Args:
            entity_types: 实体类型列表
            include_details: 是否包含详细信息
            
        Returns:
            紧凑格式的实体字符串
        """
        graph = self._load_graph()
        nodes = graph.get('nodes', [])
        
        lines = []
        for node in nodes:
            if node.get('entity_type') in entity_types:
                compact = self._format_entity_compact(node, include_details)
                lines.append(compact)
        
        return '\n'.join(lines)
    
    def convert_edges_by_type(self, edge_types: List[str],
                               include_details: bool = False) -> str:
        """
        按类型转换边为紧凑格式
        
        Args:
            edge_types: 边类型列表
            include_details: 是否包含详细信息
            
        Returns:
            紧凑格式的边字符串
        """
        graph = self._load_graph()
        edges = graph.get('edges', [])
        
        lines = []
        for edge in edges:
            if edge.get('edge_type') in edge_types:
                compact = self._format_edge_compact(edge, include_details)
                lines.append(compact)
        
        return '\n'.join(lines)
    
    def convert_all_nodes(self, include_details: bool = False) -> str:
        """
        转换所有节点为紧凑格式
        
        Args:
            include_details: 是否包含详细信息
            
        Returns:
            紧凑格式的节点字符串
        """
        graph = self._load_graph()
        nodes = graph.get('nodes', [])
        
        lines = ["Nodes:"]
        for node in nodes:
            compact = self._format_entity_compact(node, include_details)
            lines.append(f"  - {compact}")
        
        return '\n'.join(lines)
    
    def convert_all_edges(self, include_details: bool = False) -> str:
        """
        转换所有边为紧凑格式
        
        Args:
            include_details: 是否包含详细信息
            
        Returns:
            紧凑格式的边字符串
        """
        graph = self._load_graph()
        edges = graph.get('edges', [])
        
        lines = ["Edges:"]
        for edge in edges:
            compact = self._format_edge_compact(edge, include_details)
            lines.append(f"  - {compact}")
        
        return '\n'.join(lines)
    
    def convert_to_compact_graph(self, 
                                   entity_types: Optional[List[str]] = None,
                                   edge_types: Optional[List[str]] = None,
                                   include_details: bool = False) -> str:
        """
        转换整个 Graph 为紧凑格式
        
        Args:
            entity_types: 要包含的实体类型（None 表示全部）
            edge_types: 要包含的边类型（None 表示全部）
            include_details: 是否包含详细信息
            
        Returns:
            紧凑格式的 Graph 字符串
        """
        graph = self._load_graph()
        nodes = graph.get('nodes', [])
        edges = graph.get('edges', [])
        
        lines = []
        lines.append(f"Graph with {len(nodes)} nodes and {len(edges)} edges")
        
        # 转换节点
        lines.append("Nodes:")
        for node in nodes:
            if entity_types is None or node.get('entity_type') in entity_types:
                compact = self._format_entity_compact(node, include_details)
                lines.append(f"  - {compact}")
        
        # 转换边
        lines.append("Edges:")
        for edge in edges:
            if edge_types is None or edge.get('edge_type') in edge_types:
                compact = self._format_edge_compact(edge, include_details)
                lines.append(f"  - {compact}")
        
        return '\n'.join(lines)
    
    def _format_entity_compact(self, entity: Dict[str, Any], 
                                include_details: bool = False) -> str:
        """
        格式化单个实体为紧凑格式
        
        Args:
            entity: 实体数据
            include_details: 是否包含详细信息
            
        Returns:
            紧凑格式的实体字符串
        """
        entity_type = entity.get('entity_type', 'Unknown')
        
        if entity_type == 'ContainerEntity':
            container_id = entity.get('container_id', 'unknown')
            container_name = entity.get('container_name', '')
            if include_details and container_name:
                return f"Container({container_id},{container_name})"
            return f"Container({container_id})"
        
        elif entity_type == 'NPUEntity':
            npu_id = entity.get('id', 'unknown')
            cpu_affinity = entity.get('cpu_affinity', '')
            return f"NPU(id={npu_id},cpu_affinity={cpu_affinity})"
        
        elif entity_type == 'GPUEntity':
            gpu_id = entity.get('id', 'unknown')
            pci_bus_id = entity.get('pci_bus_id', '')
            return f"GPU(id={gpu_id},pci_bus_id={pci_bus_id})"
        
        elif entity_type == 'NumaEntity':
            numa_id = entity.get('numa_id', 'unknown')
            cpu_set = entity.get('cpu_set', '')
            memory_set = entity.get('memory_set', '')
            
            if include_details:
                numa_stats = entity.get('numa_stats', {})
                distance = numa_stats.get('distance_to_all_numa', {})
                if distance:
                    distance_str = ','.join([f"{k}:{v}" for k, v in sorted(distance.items())])
                    return f"[Numa {numa_id}](cpus={cpu_set},mems={memory_set},distance={{{distance_str}}})"
            
            return f"[Numa {numa_id}](cpus={cpu_set},mems={memory_set})"
        
        elif entity_type == 'NumaSetEntity':
            numa_id_str = entity.get('numa_id_str', '')
            return f"NumaSet({{{numa_id_str}}})"
        
        elif entity_type == 'ProcessEntity':
            pid = entity.get('pid', 'unknown')
            ppid = entity.get('ppid', '')
            name = entity.get('name', 'unknown')
            cmdline = entity.get('cmdline', '')
            
            if include_details and cmdline:
                cmdline_short = cmdline[:50] + '...' if len(cmdline) > 50 else cmdline
                return f"ProcessEntity(pid={pid},ppid={ppid},name={name},cmdline={cmdline_short})"
            
            return f"ProcessEntity(pid={pid},ppid={ppid},name={name})"
        
        elif entity_type == 'ThreadEntity':
            tid = entity.get('tid', 'unknown')
            name = entity.get('name', 'unknown')
            process_pid = entity.get('process_pid', '')
            
            if include_details:
                cpu_affinity = entity.get('cpu_affinity', [])
                sched = entity.get('sched_monitor', {})
                cpu_usage = sched.get('cpu_usage_pct', 0)
                return f"ThreadEntity(tid={tid},name={name},process={process_pid},cpu_affinity={cpu_affinity},cpu_usage={cpu_usage}%)"
            
            return f"ThreadEntity(tid={tid},name={name},process={process_pid})"
        
        elif entity_type == 'SocketEntity':
            socket_addr = entity.get('socket_addr', 'unknown')
            socket_port = entity.get('socket_port', '')
            socket_type = entity.get('socket_type', '')
            return f"Socket({socket_addr}:{socket_port},{socket_type})"
        
        elif entity_type == 'SharedMemoryEntity':
            shm_name = entity.get('shm_name', 'unknown')
            shm_size = entity.get('shm_size', 0)
            return f"SharedMemory(name={shm_name},size={shm_size})"
        
        else:
            # 通用格式
            unique_id = entity.get('unique_id', 'unknown')
            return f"{entity_type}({unique_id})"
    
    def _format_edge_compact(self, edge: Dict[str, Any], 
                              include_details: bool = False) -> str:
        """
        格式化单个边为紧凑格式
        
        Args:
            edge: 边数据
            include_details: 是否包含详细信息
            
        Returns:
            紧凑格式的边字符串
        """
        edge_type = edge.get('edge_type', 'Unknown')
        source = edge.get('source_node', {})
        target = edge.get('target_node', {})
        
        source_str = self._format_node_reference(source)
        target_str = self._format_node_reference(target)
        
        if include_details:
            # 添加边的详细信息
            details = []
            
            if edge_type == 'NumaAccessEdge':
                numa_info = edge.get('numa_access_info', {})
                affinity = numa_info.get('numa_affinity_info', {})
                similarity = affinity.get('cpu_mem_access_cosine_similarity', 0)
                if similarity:
                    details.append(f"similarity={similarity:.2f}")
            
            elif edge_type == 'SendToSocketEdge':
                data_flow = edge.get('data_flow', {})
                data_size = data_flow.get('data_size', 0)
                if data_size:
                    details.append(f"data_size={data_size}")
            
            if details:
                return f"{edge_type}({source_str} -> {target_str}, {', '.join(details)})"
        
        return f"{edge_type}({source_str} -> {target_str})"
    
    def _format_node_reference(self, node: Dict[str, Any]) -> str:
        """
        格式化节点引用（用于边中）
        
        Args:
            node: 节点数据
            
        Returns:
            紧凑格式的节点引用
        """
        entity_type = node.get('entity_type', 'Unknown')
        
        if entity_type == 'ProcessEntity':
            pid = node.get('pid', 'unknown')
            name = node.get('name', '')
            return f"Process({pid},{name})" if name else f"Process({pid})"
        
        elif entity_type == 'ThreadEntity':
            tid = node.get('tid', 'unknown')
            return f"Thread({tid})"
        
        elif entity_type == 'NPUEntity':
            npu_id = node.get('id', 'unknown')
            return f"NPU({npu_id})"
        
        elif entity_type == 'GPUEntity':
            gpu_id = node.get('id', 'unknown')
            return f"GPU({gpu_id})"
        
        elif entity_type == 'NumaEntity':
            numa_id = node.get('numa_id', 'unknown')
            return f"Numa({numa_id})"
        
        elif entity_type == 'NumaSetEntity':
            numa_id_str = node.get('numa_id_str', '')
            return f"NumaSet({{{numa_id_str}}})"
        
        elif entity_type == 'SocketEntity':
            socket_addr = node.get('socket_addr', 'unknown')
            socket_port = node.get('socket_port', '')
            return f"Socket({socket_addr}:{socket_port})"
        
        elif entity_type == 'ContainerEntity':
            container_id = node.get('container_id', 'unknown')
            return f"Container({container_id})"
        
        elif entity_type == 'SharedMemoryEntity':
            shm_name = node.get('shm_name', 'unknown')
            return f"SharedMemory({shm_name})"
        
        else:
            unique_id = node.get('unique_id', 'unknown')
            return f"{entity_type}({unique_id})"
    
    def convert_memory_layer_compact(self) -> str:
        """
        转换内存层数据为紧凑格式
        
        Returns:
            紧凑格式的内存层数据
        """
        memory_entity_types = ['NumaEntity', 'NumaSetEntity', 'ProcessEntity', 'ThreadEntity']
        memory_edge_types = ['NumaAccessEdge', 'AffinitativeToNuma', 'NumaSetContainEdge']
        
        return self.convert_to_compact_graph(
            entity_types=memory_entity_types,
            edge_types=memory_edge_types,
            include_details=True
        )
    
    def convert_compute_layer_compact(self) -> str:
        """
        转换计算层数据为紧凑格式
        
        Returns:
            紧凑格式的计算层数据
        """
        compute_entity_types = ['ProcessEntity', 'ThreadEntity', 'NPUEntity', 'GPUEntity']
        compute_edge_types = ['AccessEdge', 'OwnEdge', 'BelongEdge']
        
        return self.convert_to_compact_graph(
            entity_types=compute_entity_types,
            edge_types=compute_edge_types,
            include_details=True
        )
    
    def convert_network_layer_compact(self) -> str:
        """
        转换网络层数据为紧凑格式
        
        Returns:
            紧凑格式的网络层数据
        """
        network_entity_types = ['ProcessEntity', 'ThreadEntity', 'SocketEntity']
        network_edge_types = ['SendToSocketEdge', 'ConnectToEdge', 'SocketEdge']
        
        return self.convert_to_compact_graph(
            entity_types=network_entity_types,
            edge_types=network_edge_types,
            include_details=True
        )
    
    def convert_hotspot_threads_compact(self) -> str:
        """
        转换热点线程数据为紧凑格式
        
        Returns:
            紧凑格式的热点线程数据
        """
        entity_types = ['ThreadEntity', 'ProcessEntity']
        edge_types = ['OwnEdge', 'BelongEdge', 'NumaAccessEdge']
        
        return self.convert_to_compact_graph(
            entity_types=entity_types,
            edge_types=edge_types,
            include_details=True
        )


def main():
    """命令行入口"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python graph_format_converter.py <graph.json> [output.txt]")
        print("\nOptions:")
        print("  --summary         只输出摘要")
        print("  --nodes           输出所有节点")
        print("  --edges           输出所有边")
        print("  --memory          输出内存层数据")
        print("  --compute         输出计算层数据")
        print("  --network         输出网络层数据")
        print("  --hotspot         输出热点线程数据")
        print("  --details         包含详细信息")
        sys.exit(1)
    
    graph_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith('--') else None
    
    converter = GraphFormatConverter(graph_file)
    
    # 解析选项
    options = [arg for arg in sys.argv[2:] if arg.startswith('--')]
    include_details = '--details' in options
    
    # 根据选项生成输出
    if '--summary' in options:
        output = converter.convert_summary()
    elif '--nodes' in options:
        output = converter.convert_all_nodes(include_details)
    elif '--edges' in options:
        output = converter.convert_all_edges(include_details)
    elif '--memory' in options:
        output = converter.convert_memory_layer_compact()
    elif '--compute' in options:
        output = converter.convert_compute_layer_compact()
    elif '--network' in options:
        output = converter.convert_network_layer_compact()
    elif '--hotspot' in options:
        output = converter.convert_hotspot_threads_compact()
    else:
        output = converter.convert_to_compact_graph(include_details=include_details)
    
    # 输出结果
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"Output written to {output_file}")
    else:
        print(output)


if __name__ == "__main__":
    main()
