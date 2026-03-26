#include "unix_socket_common.h"

struct {
    __uint(type, BPF_MAP_TYPE_PERCPU_HASH);
    __uint(max_entries, 10240);
    __type(key, struct uds_key);
    __type(value, struct uds_stats);
} uds_stats_map_a SEC(".maps");

struct {
    __uint(type, BPF_MAP_TYPE_PERCPU_HASH);
    __uint(max_entries, 10240);
    __type(key, struct uds_key);
    __type(value, struct uds_stats);
} uds_stats_map_b SEC(".maps");

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
    __type(value, struct uds_args);
} uds_args_map SEC(".maps");

#define SOCK_STREAM 1
#define SOCK_DGRAM  2

static __always_inline void *select_stats_map(struct ipc_config *cfg)
{
    if (cfg && cfg->active_map == 1)
        return (void *)&uds_stats_map_b;
    return (void *)&uds_stats_map_a;
}

static __always_inline int update_uds_stats(void *map, struct uds_key *key,
                                             __u64 bytes, __u32 peer_inode, __u64 now)
{
    struct uds_stats *stats = bpf_map_lookup_elem(map, key);
    if (!stats) {
        struct uds_stats init = {
            .start_ns = now,
            .end_ns = now,
            .bytes = bytes,
            .count = 1,
            .peer_inode = peer_inode,
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

static __always_inline __u64 get_socket_inode(struct socket *sock)
{
    struct file *file = BPF_CORE_READ(sock, file);
    if (!file)
        return 0;
    struct inode *inode = BPF_CORE_READ(file, f_inode);
    if (!inode)
        return 0;
    return BPF_CORE_READ(inode, i_ino);
}

static __always_inline __u32 get_socket_type(struct socket *sock)
{
    struct sock *sk = BPF_CORE_READ(sock, sk);
    if (!sk)
        return 0;
    __u16 type = BPF_CORE_READ(sk, sk_type);
    return (__u32)type;
}

static __always_inline __u64 get_unix_peer_inode(struct sock *sk)
{
    struct unix_sock *usk = (struct unix_sock *)sk;
    struct sock *peer = BPF_CORE_READ(usk, peer);
    if (!peer)
        return 0;
    struct socket *peer_sock = BPF_CORE_READ(peer, sk_socket);
    if (!peer_sock)
        return 0;
    return get_socket_inode(peer_sock);
}

static __always_inline int handle_unix_sendmsg_enter(struct socket *sock, size_t size, __u8 sock_type)
{
    __u32 cfg_key = 0;
    struct ipc_config *cfg = bpf_map_lookup_elem(&config_map, &cfg_key);
    
    __u32 pid = get_pid();
    __u32 tid = get_tid();
    
    if (!check_pid_filter(cfg, pid))
        return 0;
    
    if (cfg && !cfg->enable_write)
        return 0;
    
    __u64 inode = get_socket_inode(sock);
    if (inode == 0)
        return 0;
    
    struct sock *sk = BPF_CORE_READ(sock, sk);
    __u64 peer_inode = get_unix_peer_inode(sk);
    
    struct uds_args args = {
        .inode = inode,
        .peer_inode = peer_inode,
        .timestamp = bpf_ktime_get_ns(),
        .socket_type = sock_type,
    };
    
    bpf_map_update_elem(&uds_args_map, &tid, &args, BPF_ANY);
    return 0;
}

static __always_inline int handle_unix_sendmsg_exit(ssize_t ret)
{
    if (ret <= 0)
        return 0;
    
    __u32 tid = get_tid();
    struct uds_args *args = bpf_map_lookup_elem(&uds_args_map, &tid);
    if (!args)
        return 0;
    
    bpf_map_delete_elem(&uds_args_map, &tid);
    
    __u32 cfg_key = 0;
    struct ipc_config *cfg = bpf_map_lookup_elem(&config_map, &cfg_key);
    
    struct uds_key key = {
        .pid = get_pid(),
        .tid = tid,
        .inode = args->inode,
        .socket_type = args->socket_type,
        .direction = IPC_DIR_WRITE,
    };
    
    void *stats_map = select_stats_map(cfg);
    __u64 now = bpf_ktime_get_ns();
    update_uds_stats(stats_map, &key, ret, args->peer_inode, now);
    
    return 0;
}

static __always_inline int handle_unix_recvmsg_enter(struct socket *sock, __u8 sock_type)
{
    __u32 cfg_key = 0;
    struct ipc_config *cfg = bpf_map_lookup_elem(&config_map, &cfg_key);
    
    __u32 pid = get_pid();
    __u32 tid = get_tid();
    
    if (!check_pid_filter(cfg, pid))
        return 0;
    
    if (cfg && !cfg->enable_read)
        return 0;
    
    __u64 inode = get_socket_inode(sock);
    if (inode == 0)
        return 0;
    
    struct sock *sk = BPF_CORE_READ(sock, sk);
    __u64 peer_inode = get_unix_peer_inode(sk);
    
    struct uds_args args = {
        .inode = inode,
        .peer_inode = peer_inode,
        .timestamp = bpf_ktime_get_ns(),
        .socket_type = sock_type,
    };
    
    bpf_map_update_elem(&uds_args_map, &tid, &args, BPF_ANY);
    return 0;
}

static __always_inline int handle_unix_recvmsg_exit(ssize_t ret)
{
    if (ret <= 0)
        return 0;
    
    __u32 tid = get_tid();
    struct uds_args *args = bpf_map_lookup_elem(&uds_args_map, &tid);
    if (!args)
        return 0;
    
    bpf_map_delete_elem(&uds_args_map, &tid);
    
    __u32 cfg_key = 0;
    struct ipc_config *cfg = bpf_map_lookup_elem(&config_map, &cfg_key);
    
    struct uds_key key = {
        .pid = get_pid(),
        .tid = tid,
        .inode = args->inode,
        .socket_type = args->socket_type,
        .direction = IPC_DIR_READ,
    };
    
    void *stats_map = select_stats_map(cfg);
    __u64 now = bpf_ktime_get_ns();
    update_uds_stats(stats_map, &key, ret, args->peer_inode, now);
    
    return 0;
}

SEC("kprobe/unix_stream_sendmsg")
int BPF_KPROBE(k_unix_stream_sendmsg, struct socket *sock, struct msghdr *msg, size_t size)
{
    return handle_unix_sendmsg_enter(sock, size, SOCK_STREAM);
}

SEC("kretprobe/unix_stream_sendmsg")
int BPF_KRETPROBE(kr_unix_stream_sendmsg, int ret)
{
    return handle_unix_sendmsg_exit((ssize_t)ret);
}

SEC("kprobe/unix_stream_recvmsg")
int BPF_KPROBE(k_unix_stream_recvmsg, struct socket *sock, struct msghdr *msg, size_t size, int flags)
{
    return handle_unix_recvmsg_enter(sock, SOCK_STREAM);
}

SEC("kretprobe/unix_stream_recvmsg")
int BPF_KRETPROBE(kr_unix_stream_recvmsg, int ret)
{
    return handle_unix_recvmsg_exit((ssize_t)ret);
}

SEC("kprobe/unix_dgram_sendmsg")
int BPF_KPROBE(k_unix_dgram_sendmsg, struct socket *sock, struct msghdr *msg, size_t size)
{
    return handle_unix_sendmsg_enter(sock, size, SOCK_DGRAM);
}

SEC("kretprobe/unix_dgram_sendmsg")
int BPF_KRETPROBE(kr_unix_dgram_sendmsg, int ret)
{
    return handle_unix_sendmsg_exit((ssize_t)ret);
}

SEC("kprobe/unix_dgram_recvmsg")
int BPF_KPROBE(k_unix_dgram_recvmsg, struct socket *sock, struct msghdr *msg, size_t size, int flags)
{
    return handle_unix_recvmsg_enter(sock, SOCK_DGRAM);
}

SEC("kretprobe/unix_dgram_recvmsg")
int BPF_KRETPROBE(kr_unix_dgram_recvmsg, int ret)
{
    return handle_unix_recvmsg_exit((ssize_t)ret);
}

char LICENSE[] SEC("license") = "GPL";
