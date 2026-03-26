#include "posix_mq_common.h"

struct {
    __uint(type, BPF_MAP_TYPE_PERCPU_HASH);
    __uint(max_entries, 10240);
    __type(key, struct posix_mq_key);
    __type(value, struct posix_mq_stats);
} posix_mq_stats_map_a SEC(".maps");

struct {
    __uint(type, BPF_MAP_TYPE_PERCPU_HASH);
    __uint(max_entries, 10240);
    __type(key, struct posix_mq_key);
    __type(value, struct posix_mq_stats);
} posix_mq_stats_map_b SEC(".maps");

struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, 1);
    __type(key, __u32);
    __type(value, struct ipc_config);
} config_map SEC(".maps");

struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 1024);
    __type(key, __u32);
    __type(value, struct posix_mq_args);
} mq_args_map SEC(".maps");

static __always_inline void *select_stats_map(struct ipc_config *cfg)
{
    if (cfg && cfg->active_map == 1)
        return (void *)&posix_mq_stats_map_b;
    return (void *)&posix_mq_stats_map_a;
}

static __always_inline int update_mq_stats(void *map, struct posix_mq_key *key,
                                            __u64 bytes, __u32 msg_prio, __u64 now)
{
    struct posix_mq_stats *stats = bpf_map_lookup_elem(map, key);
    if (!stats) {
        struct posix_mq_stats init = {
            .start_ns = now,
            .end_ns = now,
            .bytes = bytes,
            .count = 1,
            .msg_prio = msg_prio,
            .padding = 0,
        };
        bpf_map_update_elem(map, key, &init, BPF_ANY);
    } else {
        stats->bytes += bytes;
        stats->end_ns = now;
        stats->count += 1;
    }
    return 0;
}

SEC("tp/syscalls/sys_enter_mq_timedsend")
int trace_mq_send_enter(struct trace_event_raw_sys_enter *ctx)
{
    int mqdes = (int)ctx->args[0];
    size_t msg_len = (size_t)ctx->args[2];
    unsigned int msg_prio = (unsigned int)ctx->args[3];

    __u32 cfg_key = 0;
    struct ipc_config *cfg = bpf_map_lookup_elem(&config_map, &cfg_key);
    
    __u32 pid = get_pid();
    __u32 tid = get_tid();
    
    if (!check_pid_filter(cfg, pid))
        return 0;

    struct posix_mq_args args = {
        .mqd = mqdes,
        .msg_prio = msg_prio,
        .timestamp = bpf_ktime_get_ns(),
        .msg_len = msg_len,
    };

    bpf_map_update_elem(&mq_args_map, &tid, &args, BPF_ANY);
    return 0;
}

SEC("tp/syscalls/sys_exit_mq_timedsend")
int trace_mq_send_exit(struct trace_event_raw_sys_exit *ctx)
{
    long ret = ctx->ret;
    
    __u32 tid = get_tid();
    struct posix_mq_args *args = bpf_map_lookup_elem(&mq_args_map, &tid);
    if (!args)
        return 0;

    bpf_map_delete_elem(&mq_args_map, &tid);

    if (ret != 0)
        return 0;

    __u32 cfg_key = 0;
    struct ipc_config *cfg = bpf_map_lookup_elem(&config_map, &cfg_key);
    
    if (cfg && !cfg->enable_write)
        return 0;

    struct posix_mq_key key = {
        .pid = get_pid(),
        .tid = tid,
        .mqd = args->mqd,
        .direction = IPC_DIR_WRITE,
    };

    void *stats_map = select_stats_map(cfg);
    __u64 now = bpf_ktime_get_ns();
    update_mq_stats(stats_map, &key, args->msg_len, args->msg_prio, now);

    return 0;
}

SEC("tp/syscalls/sys_enter_mq_timedreceive")
int trace_mq_recv_enter(struct trace_event_raw_sys_enter *ctx)
{
    int mqdes = (int)ctx->args[0];
    size_t msg_len = (size_t)ctx->args[2];

    __u32 cfg_key = 0;
    struct ipc_config *cfg = bpf_map_lookup_elem(&config_map, &cfg_key);
    
    __u32 pid = get_pid();
    __u32 tid = get_tid();
    
    if (!check_pid_filter(cfg, pid))
        return 0;

    struct posix_mq_args args = {
        .mqd = mqdes,
        .msg_prio = 0,
        .timestamp = bpf_ktime_get_ns(),
        .msg_len = msg_len,
    };

    bpf_map_update_elem(&mq_args_map, &tid, &args, BPF_ANY);
    return 0;
}

SEC("tp/syscalls/sys_exit_mq_timedreceive")
int trace_mq_recv_exit(struct trace_event_raw_sys_exit *ctx)
{
    ssize_t ret = (ssize_t)ctx->ret;
    
    __u32 tid = get_tid();
    struct posix_mq_args *args = bpf_map_lookup_elem(&mq_args_map, &tid);
    if (!args)
        return 0;

    bpf_map_delete_elem(&mq_args_map, &tid);

    if (ret < 0)
        return 0;

    __u32 cfg_key = 0;
    struct ipc_config *cfg = bpf_map_lookup_elem(&config_map, &cfg_key);
    
    if (cfg && !cfg->enable_read)
        return 0;

    struct posix_mq_key key = {
        .pid = get_pid(),
        .tid = tid,
        .mqd = args->mqd,
        .direction = IPC_DIR_READ,
    };

    void *stats_map = select_stats_map(cfg);
    __u64 now = bpf_ktime_get_ns();
    update_mq_stats(stats_map, &key, ret, args->msg_prio, now);

    return 0;
}

char LICENSE[] SEC("license") = "GPL";
