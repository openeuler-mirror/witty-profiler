#pragma once

// 定义一个函数 get_socket_sniffer_lru_style 以备查询对比
// 具体实现由 不同的.c文件完成

#if !defined(__VMLINUX_H__)
#include <linux/types.h>
#endif

enum SocketSnifferLruStyle
{
	SOCKET_SNIFFER_LRU_FIXED = 1,
	SOCKET_SNIFFER_LRU_DYNAMIC = 2,
};

struct socket_sniffer_version
{
	__u32 lru_style;
};

__u32 get_socket_sniffer_lru_style();
extern const volatile struct socket_sniffer_version socket_sniffer_version;