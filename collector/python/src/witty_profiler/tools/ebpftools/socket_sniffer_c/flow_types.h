#pragma once

#include <linux/types.h>

struct flow_key
{
    __u32 pid;
    __u32 tid;
    __u32 saddr;
    __u32 daddr;
    __u16 sport;
    __u16 dport;
    __u8 proto;
    __u8 func_id;
};

struct flow_stats_val
{
    __u64 start_ns;
    __u64 end_ns;
    __u64 bytes;
    __u64 pkts;
};

struct config
{
    __u32 target_pid;
    __u8 enable_send;
    __u8 enable_recv;
    __u8 active_map;
    __u8 compress_msg;
};
