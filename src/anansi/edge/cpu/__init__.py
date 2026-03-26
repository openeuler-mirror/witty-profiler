"""CPU-related edges and sniffers for topology detection.

This module provides edges and sniffers for CPU-related metrics:
- NUMA access tracking
- HCCS bandwidth monitoring (Huawei Kunpeng)
- Cache and scheduling monitoring

Note:
    Heavy dependencies (pandas, numpy) are NOT imported in __init__.py.
    Import specific modules directly to avoid unnecessary dependency loading:

    ```python
    # Instead of:
    from anansi.edge.cpu import NumaSniffer

    # Use:
    from anansi.edge.cpu.numa_sniffer import NumaSniffer
    ```
"""

from .hccs_edge import (
    DDRBandwidthEdge,
    DDRBandwidthInfo,
    HHABandwidthEdge,
    HHABandwidthInfo,
    HCCSBandwidthEdge,
    HCCSBandwidthInfo,
    HCCSStream,
    L3CBandwidthEdge,
    L3CBandwidthInfo,
    PABandwidthEdge,
    PABandwidthInfo,
)
from .hccs_sniffer import HCCSBandwidthSnapshot, HCCSSniffer, get_hccs_sniffer
from .numa_edge import AffinitativeToNuma, NumaAccessEdge

__all__ = [
    "HCCSStream",
    "HCCSBandwidthInfo",
    "DDRBandwidthInfo",
    "HHABandwidthInfo",
    "L3CBandwidthInfo",
    "PABandwidthInfo",
    "HCCSBandwidthEdge",
    "DDRBandwidthEdge",
    "HHABandwidthEdge",
    "L3CBandwidthEdge",
    "PABandwidthEdge",
    "HCCSBandwidthSnapshot",
    "HCCSSniffer",
    "get_hccs_sniffer",
    "AffinitativeToNuma",
    "NumaAccessEdge",
]
