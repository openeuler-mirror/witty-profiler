#include "sysv_msg_common.h"

struct {
    __uint(type, BPF_MAP_TYPE_PERCPU_HASH);
    __uint(max_entries, 10240);
    __type(key, struct sysv_msg_key);
    __type(value, struct sysv_msg_stats);
} sysv_msg_stats_map_a SEC(".maps");

struct {
    __uint(type, BPF_MAP_TYPE_PERCPU_HASH);
    __uint(max_entries, 10240);
    __type(key, struct sysv_msg_key);
    __type(value, struct sysv_msg_stats);
} sysv_msg_stats_map_b SEC(".maps");

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
    __type(value, struct sysv_msg_args);
} msg_args_map SEC(".maps");

static __always_inline void *select_stats_map(struct ipc_config *cfg)
{
    if (cfg && cfg->active_map == 1)
        return (void *)&sysv_msg_stats_map_b;
    return (void *)&sysv_msg_stats_map_a;
}

static __always_inline int update_msg_stats(void *map, struct sysv_msg_key *key,
                                             __u64 bytes, __s32 msg_type, __u64 now)
{
    struct sysv_msg_stats *stats = bpf_map_lookup_elem(map, key);
    if (!stats) {
        struct sysv_msg_stats init = {
            .start_ns = now,
            .end_ns = now,
            .bytes = bytes,
            .count = 1,
            .msg_type = msg_type,
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

SEC("tp/syscalls/sys_enter_msgsnd")
int trace_msgsnd_enter(struct trace_event_raw_sys_enter *ctx)
{
    int msqid = (int)ctx->args[0];
    const void *msgp = (const void *)ctx->args[1];
    size_t msgsz = (size_t)ctx->args[2];

    __u32 cfg_key = 0;
    struct ipc_config *cfg = bpf_map_lookup_elem(&config_map, &cfg_key);
    
    __u32 pid = get_pid();
    __u32 tid = get_tid();
    
    if (!check_pid_filter(cfg, pid))
        return 0;

    struct sysv_msg_args args = {
        .msqid = msqid,
        .msg_type = 0,
        .timestamp = bpf_ktime_get_ns(),
        .msgsz = msgsz,
    };

    if (msgp) {
        bpf_probe_read_user(&args.msg_type, sizeof(args.msg_type), msgp);
    }

    bpf_map_update_elem(&msg_args_map, &tid, &args, BPF_ANY);
    return 0;
}

SEC("tp/syscalls/sys_exit_msgsnd")
int trace_msgsnd_exit(struct trace_event_raw_sys_exit *ctx)
{
    long ret = ctx->ret;
    
    __u32 tid = get_tid();
    struct sysv_msg_args *args = bpf_map_lookup_elem(&msg_args_map, &tid);
    if (!args)
        return 0;

    bpf_map_delete_elem(&msg_args_map, &tid);

    if (ret != 0)
        return 0;

    __u32 cfg_key = 0;
    struct ipc_config *cfg = bpf_map_lookup_elem(&config_map, &cfg_key);
    
    if (cfg && !cfg->enable_write)
        return 0;

    struct sysv_msg_key key = {
        .pid = get_pid(),
        .tid = tid,
        .msqid = args->msqid,
        .direction = IPC_DIR_WRITE,
    };

    void *stats_map = select_stats_map(cfg);
    __u64 now = bpf_ktime_get_ns();
    update_msg_stats(stats_map, &key, args->msgsz, args->msg_type, now);

    return 0;
}

SEC("tp/syscalls/sys_enter_msgrcv")
int trace_msgrcv_enter(struct trace_event_raw_sys_enter *ctx)
{
    int msqid = (int)ctx->args[0];
    size_t msgsz = (size_t)ctx->args[2];
    long msgtyp = (long)ctx->args[3];

    __u32 cfg_key = 0;
    struct ipc_config *cfg = bpf_map_lookup_elem(&config_map, &cfg_key);
    
    __u32 pid = get_pid();
    __u32 tid = get_tid();
    
    if (!check_pid_filter(cfg, pid))
        return 0;

    struct sysv_msg_args args = {
        .msqid = msqid,
        .msg_type = (__s32)msgtyp,
        .timestamp = bpf_ktime_get_ns(),
        .msgsz = msgsz,
    };

    bpf_map_update_elem(&msg_args_map, &tid, &args, BPF_ANY);
    return 0;
}

SEC("tp/syscalls/sys_exit_msgrcv")
int trace_msgrcv_exit(struct trace_event_raw_sys_exit *ctx)
{
    ssize_t ret = (ssize_t)ctx->ret;
    
    __u32 tid = get_tid();
    struct sysv_msg_args *args = bpf_map_lookup_elem(&msg_args_map, &tid);
    if (!args)
        return 0;

    bpf_map_delete_elem(&msg_args_map, &tid);

    if (ret < 0)
        return 0;

    __u32 cfg_key = 0;
    struct ipc_config *cfg = bpf_map_lookup_elem(&config_map, &cfg_key);
    
    if (cfg && !cfg->enable_read)
        return 0;

    struct sysv_msg_key key = {
        .pid = get_pid(),
        .tid = tid,
        .msqid = args->msqid,
        .direction = IPC_DIR_READ,
    };

    void *stats_map = select_stats_map(cfg);
    __u64 now = bpf_ktime_get_ns();
    update_msg_stats(stats_map, &key, ret, args->msg_type, now);

    return 0;
}

char LICENSE[] SEC("license") = "GPL";
