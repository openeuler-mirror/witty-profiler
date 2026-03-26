#ifndef IPC_COMMON_H
#define IPC_COMMON_H

#include "vmlinux.h"

#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>
#include <bpf/bpf_core_read.h>

#ifndef NULL
#define NULL ((void *)0)
#endif

struct ipc_config {
    __u32 target_pid;
    __u32 target_tgid;
    __u8  enable_write;
    __u8  enable_read;
    __u8  active_map;
    __u8  reserved;
};

struct ipc_stats_base {
    __u64 start_ns;
    __u64 end_ns;
    __u64 bytes;
    __u64 count;
};

static __always_inline __u64 get_pid_tgid(void)
{
    return bpf_get_current_pid_tgid();
}

static __always_inline __u32 get_pid(void)
{
    return (__u32)(bpf_get_current_pid_tgid() >> 32);
}

static __always_inline __u32 get_tid(void)
{
    return (__u32)bpf_get_current_pid_tgid();
}

static __always_inline int check_pid_filter(struct ipc_config *cfg, __u32 pid)
{
    if (!cfg)
        return 1;
    if (cfg->target_pid && cfg->target_pid != pid)
        return 0;
    return 1;
}

static __always_inline int check_tgid_filter(struct ipc_config *cfg, __u32 tgid)
{
    if (!cfg)
        return 1;
    if (cfg->target_tgid && cfg->target_tgid != tgid)
        return 0;
    return 1;
}

#endif
