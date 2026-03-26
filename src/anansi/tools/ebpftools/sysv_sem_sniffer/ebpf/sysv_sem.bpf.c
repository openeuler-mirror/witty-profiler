#include "sysv_sem_common.h"

struct {
    __uint(type, BPF_MAP_TYPE_PERCPU_HASH);
    __uint(max_entries, 10240);
    __type(key, struct sysv_sem_key);
    __type(value, struct sysv_sem_stats);
} sysv_sem_stats_map_a SEC(".maps");

struct {
    __uint(type, BPF_MAP_TYPE_PERCPU_HASH);
    __uint(max_entries, 10240);
    __type(key, struct sysv_sem_key);
    __type(value, struct sysv_sem_stats);
} sysv_sem_stats_map_b SEC(".maps");

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
    __type(value, struct sysv_sem_args);
} sem_args_map SEC(".maps");

static __always_inline void *select_stats_map(struct ipc_config *cfg)
{
    if (cfg && cfg->active_map == 1)
        return (void *)&sysv_sem_stats_map_b;
    return (void *)&sysv_sem_stats_map_a;
}

static __always_inline int update_sem_stats(void *map, struct sysv_sem_key *key,
                                             __s16 sem_op_val, __u16 sem_flg, __u64 now)
{
    struct sysv_sem_stats *stats = bpf_map_lookup_elem(map, key);
    if (!stats) {
        struct sysv_sem_stats init = {
            .start_ns = now,
            .end_ns = now,
            .count = 1,
            .sem_op_val = sem_op_val,
            .sem_flg = sem_flg,
            .padding = 0,
        };
        bpf_map_update_elem(map, key, &init, BPF_ANY);
    } else {
        stats->end_ns = now;
        stats->count += 1;
    }
    return 0;
}

SEC("tp/syscalls/sys_enter_semop")
int trace_semop_enter(struct trace_event_raw_sys_enter *ctx)
{
    int semid = (int)ctx->args[0];
    struct sembuf_user *sops = (struct sembuf_user *)ctx->args[1];
    unsigned nsops = (unsigned)ctx->args[2];

    __u32 cfg_key = 0;
    struct ipc_config *cfg = bpf_map_lookup_elem(&config_map, &cfg_key);
    
    __u32 pid = get_pid();
    __u32 tid = get_tid();
    
    if (!check_pid_filter(cfg, pid))
        return 0;

    struct sysv_sem_args args = {
        .timestamp = bpf_ktime_get_ns(),
        .semid = semid,
        .sem_num = 0,
        .sem_op = 0,
        .sem_flg = 0,
        .padding1 = 0,
        .padding2 = 0,
    };

    if (sops && nsops > 0) {
        struct sembuf_user sop;
        if (bpf_probe_read_user(&sop, sizeof(sop), sops) == 0) {
            args.sem_num = sop.sem_num;
            args.sem_op = sop.sem_op;
            args.sem_flg = sop.sem_flg;
        }
    }

    bpf_map_update_elem(&sem_args_map, &tid, &args, BPF_ANY);
    return 0;
}

SEC("tp/syscalls/sys_exit_semop")
int trace_semop_exit(struct trace_event_raw_sys_exit *ctx)
{
    long ret = ctx->ret;
    
    __u32 tid = get_tid();
    struct sysv_sem_args *args = bpf_map_lookup_elem(&sem_args_map, &tid);
    if (!args)
        return 0;

    bpf_map_delete_elem(&sem_args_map, &tid);

    if (ret != 0)
        return 0;

    __u32 cfg_key = 0;
    struct ipc_config *cfg = bpf_map_lookup_elem(&config_map, &cfg_key);

    __u16 sem_op_type = 0;
    if (args->sem_op > 0)
        sem_op_type = 1;
    else if (args->sem_op < 0)
        sem_op_type = 2;

    struct sysv_sem_key key = {
        .pid = get_pid(),
        .tid = tid,
        .semid = args->semid,
        .sem_num = args->sem_num,
        .sem_op_type = sem_op_type,
    };

    void *stats_map = select_stats_map(cfg);
    __u64 now = bpf_ktime_get_ns();
    update_sem_stats(stats_map, &key, args->sem_op, args->sem_flg, now);

    return 0;
}

SEC("tp/syscalls/sys_enter_semtimedop")
int trace_semtimedop_enter(struct trace_event_raw_sys_enter *ctx)
{
    int semid = (int)ctx->args[0];
    struct sembuf_user *sops = (struct sembuf_user *)ctx->args[1];
    unsigned nsops = (unsigned)ctx->args[2];

    __u32 cfg_key = 0;
    struct ipc_config *cfg = bpf_map_lookup_elem(&config_map, &cfg_key);
    
    __u32 pid = get_pid();
    __u32 tid = get_tid();
    
    if (!check_pid_filter(cfg, pid))
        return 0;

    struct sysv_sem_args args = {
        .timestamp = bpf_ktime_get_ns(),
        .semid = semid,
        .sem_num = 0,
        .sem_op = 0,
        .sem_flg = 0,
        .padding1 = 0,
        .padding2 = 0,
    };

    if (sops && nsops > 0) {
        struct sembuf_user sop;
        if (bpf_probe_read_user(&sop, sizeof(sop), sops) == 0) {
            args.sem_num = sop.sem_num;
            args.sem_op = sop.sem_op;
            args.sem_flg = sop.sem_flg;
        }
    }

    bpf_map_update_elem(&sem_args_map, &tid, &args, BPF_ANY);
    return 0;
}

SEC("tp/syscalls/sys_exit_semtimedop")
int trace_semtimedop_exit(struct trace_event_raw_sys_exit *ctx)
{
    long ret = ctx->ret;
    
    __u32 tid = get_tid();
    struct sysv_sem_args *args = bpf_map_lookup_elem(&sem_args_map, &tid);
    if (!args)
        return 0;

    bpf_map_delete_elem(&sem_args_map, &tid);

    if (ret != 0)
        return 0;

    __u32 cfg_key = 0;
    struct ipc_config *cfg = bpf_map_lookup_elem(&config_map, &cfg_key);

    __u16 sem_op_type = 0;
    if (args->sem_op > 0)
        sem_op_type = 1;
    else if (args->sem_op < 0)
        sem_op_type = 2;

    struct sysv_sem_key key = {
        .pid = get_pid(),
        .tid = tid,
        .semid = args->semid,
        .sem_num = args->sem_num,
        .sem_op_type = sem_op_type,
    };

    void *stats_map = select_stats_map(cfg);
    __u64 now = bpf_ktime_get_ns();
    update_sem_stats(stats_map, &key, args->sem_op, args->sem_flg, now);

    return 0;
}

char LICENSE[] SEC("license") = "GPL";
