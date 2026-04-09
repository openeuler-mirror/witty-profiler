"""
Thread Profile Builder

本脚本提供线程画像构建的辅助函数，用于从 Anansi Graph 中提取线程性能数据。
不包含分析逻辑，仅提供数据提取接口。

Usage:
    from thread_profile_builder import extract_thread_metrics, extract_process_metrics
    
    thread_data = extract_thread_metrics(thread_entity)
    process_data = extract_process_metrics(process_entity)
"""

from typing import Dict, List, Any, Optional


def extract_thread_metrics(thread_entity: Dict[str, Any]) -> Dict[str, Any]:
    """
    从 ThreadEntity 中提取性能指标（不包含分析逻辑）
    
    Args:
        thread_entity: ThreadEntity 数据
        
    Returns:
        线程性能指标字典
    """
    metrics = {
        'tid': thread_entity.get('tid'),
        'name': thread_entity.get('name', 'unknown'),
        'process_pid': thread_entity.get('process_pid'),
        'cpu_affinity': thread_entity.get('cpu_affinity', []),
        'cpu_usage': 0.0,
        'ctx_switches': {
            'voluntary': 0,
            'involuntary': 0,
            'total': 0
        },
        'numa_access': {
            'remote_ratio': 0.0,
            'local_ratio': 1.0,
            'numa_nodes': []
        },
        'cache_miss': {
            'l1i_rate': 0.0,
            'llc_rate': 0.0
        }
    }
    
    sched_data = thread_entity.get('sched_monitor', {})
    if sched_data:
        metrics['cpu_usage'] = sched_data.get('cpu_usage_pct', 0.0)
        metrics['ctx_switches'] = {
            'voluntary': sched_data.get('voluntary_ctxt_switches', 0),
            'involuntary': sched_data.get('nonvoluntary_ctxt_switches', 0),
            'total': sched_data.get('voluntary_ctxt_switches', 0) + sched_data.get('nonvoluntary_ctxt_switches', 0)
        }
    
    numa_data = thread_entity.get('numa_access_info', {})
    if numa_data:
        affinity_info = numa_data.get('numa_affinity_info', {})
        metrics['numa_access'] = {
            'remote_ratio': 1.0 - affinity_info.get('cpu_mem_access_cosine_similarity', 1.0),
            'local_ratio': affinity_info.get('cpu_mem_access_cosine_similarity', 1.0),
            'numa_nodes': affinity_info.get('mem_pages_in_each_numa', [])
        }
    
    cache_data = thread_entity.get('cache_monitor', {})
    if cache_data:
        metrics['cache_miss'] = {
            'l1i_rate': cache_data.get('l1i_miss_rate', 0.0),
            'llc_rate': cache_data.get('llc_miss_rate', 0.0)
        }
    
    return metrics


def extract_process_metrics(process_entity: Dict[str, Any]) -> Dict[str, Any]:
    """
    从 ProcessEntity 中提取性能指标（不包含分析逻辑）
    
    Args:
        process_entity: ProcessEntity 数据
        
    Returns:
        进程性能指标字典
    """
    metrics = {
        'pid': process_entity.get('pid'),
        'ppid': process_entity.get('ppid'),
        'name': process_entity.get('name', 'unknown'),
        'cmdline': process_entity.get('cmdline', ''),
        'num_threads': process_entity.get('num_threads', 0),
        'cpu_usage': 0.0,
        'memory_mb': 0.0,
        'threads': []
    }
    
    sched_data = process_entity.get('sched_monitor', {})
    if sched_data:
        metrics['cpu_usage'] = sched_data.get('cpu_usage_pct', 0.0)
    
    mem_data = process_entity.get('memory_info', {})
    if mem_data:
        metrics['memory_mb'] = mem_data.get('rss_mb', 0.0)
    
    return metrics
