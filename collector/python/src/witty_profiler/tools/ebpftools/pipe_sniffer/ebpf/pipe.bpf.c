#include "pipe_common.h"

struct {
    __uint(type, BPF_MAP_TYPE_PERCPU_HASH);
    __uint(max_entries, 10240);
    __type(key, struct pipe_key);
    __type(value, struct pipe_stats);
} pipe_stats_map_a SEC(".maps");

struct {
    __uint(type, BPF_MAP_TYPE_PERCPU_HASH);
    __uint(max_entries, 10240);
    __type(key, struct pipe_key);
    __type(value, struct pipe_stats);
} pipe_stats_map_b SEC(".maps");

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
    __type(value, struct pipe_args);
} pipe_args_map SEC(".maps");

static __always_inline void *select_stats_map(struct ipc_config *cfg)
{
    if (cfg && cfg->active_map == 1)
        return (void *)&pipe_stats_map_b;
    return (void *)&pipe_stats_map_a;
}

static __always_inline int update_pipe_stats(void *map, struct pipe_key *key, 
                                              __u64 bytes, __u64 now)
{
    struct pipe_stats *stats = bpf_map_lookup_elem(map, key);
    if (!stats) {
        struct pipe_stats init = {
            .start_ns = now,
            .end_ns = now,
            .bytes = bytes,
            .count = 1,
        };
        bpf_map_update_elem(map, key, &init, BPF_ANY);
    } else {
        stats->bytes += bytes;
        stats->end_ns = now;
        stats->count += 1;
    }
    return 0;
}

static __always_inline int handle_pipe_write_enter(struct kiocb *iocb)
{
    __u32 cfg_key = 0;
    struct ipc_config *cfg = bpf_map_lookup_elem(&config_map, &cfg_key);
    
    __u32 pid = get_pid();
    __u32 tid = get_tid();
    
    if (!check_pid_filter(cfg, pid))
        return 0;
    
    struct file *file = BPF_CORE_READ(iocb, ki_filp);
    if (!file)
        return 0;
    
    struct inode *inode = BPF_CORE_READ(file, f_inode);
    if (!inode)
        return 0;
    
    __u64 ino = BPF_CORE_READ(inode, i_ino);
    
    umode_t mode = BPF_CORE_READ(inode, i_mode);
    __u8 is_fifo = (mode & 0010000) ? 1 : 0;
    
    struct pipe_args args = {
        .inode = ino,
        .timestamp = bpf_ktime_get_ns(),
        .direction = IPC_DIR_WRITE,
        .is_fifo = is_fifo,
    };
    
    bpf_map_update_elem(&pipe_args_map, &tid, &args, BPF_ANY);
    return 0;
}

static __always_inline int handle_pipe_write_exit(ssize_t ret)
{
    if (ret <= 0)
        return 0;
    
    __u32 tid = get_tid();
    struct pipe_args *args = bpf_map_lookup_elem(&pipe_args_map, &tid);
    if (!args)
        return 0;
    
    __u32 cfg_key = 0;
    struct ipc_config *cfg = bpf_map_lookup_elem(&config_map, &cfg_key);
    
    if (cfg && !cfg->enable_write) {
        bpf_map_delete_elem(&pipe_args_map, &tid);
        return 0;
    }
    
    struct pipe_key key = {
        .pid = get_pid(),
        .tid = tid,
        .inode = args->inode,
        .direction = IPC_DIR_WRITE,
        .is_fifo = args->is_fifo,
    };
    
    void *stats_map = select_stats_map(cfg);
    __u64 now = bpf_ktime_get_ns();
    update_pipe_stats(stats_map, &key, ret, now);
    
    bpf_map_delete_elem(&pipe_args_map, &tid);
    return 0;
}

static __always_inline int handle_pipe_read_enter(struct kiocb *iocb)
{
    __u32 cfg_key = 0;
    struct ipc_config *cfg = bpf_map_lookup_elem(&config_map, &cfg_key);
    
    __u32 pid = get_pid();
    __u32 tid = get_tid();
    
    if (!check_pid_filter(cfg, pid))
        return 0;
    
    struct file *file = BPF_CORE_READ(iocb, ki_filp);
    if (!file)
        return 0;
    
    struct inode *inode = BPF_CORE_READ(file, f_inode);
    if (!inode)
        return 0;
    
    __u64 ino = BPF_CORE_READ(inode, i_ino);
    
    umode_t mode = BPF_CORE_READ(inode, i_mode);
    __u8 is_fifo = (mode & 0010000) ? 1 : 0;
    
    struct pipe_args args = {
        .inode = ino,
        .timestamp = bpf_ktime_get_ns(),
        .direction = IPC_DIR_READ,
        .is_fifo = is_fifo,
    };
    
    bpf_map_update_elem(&pipe_args_map, &tid, &args, BPF_ANY);
    return 0;
}

static __always_inline int handle_pipe_read_exit(ssize_t ret)
{
    if (ret <= 0)
        return 0;
    
    __u32 tid = get_tid();
    struct pipe_args *args = bpf_map_lookup_elem(&pipe_args_map, &tid);
    if (!args)
        return 0;
    
    __u32 cfg_key = 0;
    struct ipc_config *cfg = bpf_map_lookup_elem(&config_map, &cfg_key);
    
    if (cfg && !cfg->enable_read) {
        bpf_map_delete_elem(&pipe_args_map, &tid);
        return 0;
    }
    
    struct pipe_key key = {
        .pid = get_pid(),
        .tid = tid,
        .inode = args->inode,
        .direction = IPC_DIR_READ,
        .is_fifo = args->is_fifo,
    };
    
    void *stats_map = select_stats_map(cfg);
    __u64 now = bpf_ktime_get_ns();
    update_pipe_stats(stats_map, &key, ret, now);
    
    bpf_map_delete_elem(&pipe_args_map, &tid);
    return 0;
}

SEC("kprobe/pipe_write")
int BPF_KPROBE(k_pipe_write, struct kiocb *iocb, const struct iovec *iov,
               unsigned long nr_segs, loff_t pos)
{
    return handle_pipe_write_enter(iocb);
}

SEC("kretprobe/pipe_write")
int BPF_KRETPROBE(kr_pipe_write, ssize_t ret)
{
    return handle_pipe_write_exit(ret);
}

SEC("kprobe/pipe_read")
int BPF_KPROBE(k_pipe_read, struct kiocb *iocb, const struct iovec *iov,
               unsigned long nr_segs, loff_t pos)
{
    return handle_pipe_read_enter(iocb);
}

SEC("kretprobe/pipe_read")
int BPF_KRETPROBE(kr_pipe_read, ssize_t ret)
{
    return handle_pipe_read_exit(ret);
}

char LICENSE[] SEC("license") = "GPL";
