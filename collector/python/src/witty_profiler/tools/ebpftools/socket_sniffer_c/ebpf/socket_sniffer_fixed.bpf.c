// eBPF program to aggregate per-flow send statistics for a target PID (if provided).
// Fixed LRU maps (two per-cpu hash maps)
#include "socket_sniffer_common.h"
#include "socket_sniffer_version.h"

struct {
    __uint(type, BPF_MAP_TYPE_PERCPU_HASH);
    __uint(max_entries, 10240);
    __type(key, struct flow_key);
    __type(value, struct flow_stats_val);
} flow_stats_map_a SEC(".maps");

struct {
    __uint(type, BPF_MAP_TYPE_PERCPU_HASH);
    __uint(max_entries, 10240);
    __type(key, struct flow_key);
    __type(value, struct flow_stats_val);
} flow_stats_map_b SEC(".maps");

struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, 1);
    __type(key, __u32);
    __type(value, struct config);
} config_map SEC(".maps");

struct recv_args_map_def recv_args_map SEC(".maps");

__u32 get_socket_sniffer_lru_style()
{
    return SOCKET_SNIFFER_LRU_FIXED;
}

const volatile struct socket_sniffer_version socket_sniffer_version = {
    .lru_style = SOCKET_SNIFFER_LRU_FIXED,
};

static __always_inline void *select_stats_map(struct config *cfg)
{
    bool use_b = cfg && cfg->active_map == 1;
    return use_b ? (void *)&flow_stats_map_b : (void *)&flow_stats_map_a;
}

static __always_inline int socket_recv_exit_fixed(__s64 ret,
                                                  __u8 proto,
                                                  __u8 func,
                                                  bool fill_remote_hint)
{
    __u32 tid = (__u32)bpf_get_current_pid_tgid();
    struct recv_args *args = bpf_map_lookup_elem(&recv_args_map, &tid);
    __u32 cfg_key = 0;
    struct config *cfg = bpf_map_lookup_elem(&config_map, &cfg_key);
    /* 区别: select between two pre-allocated LRU maps */
    void *stats_map = select_stats_map(cfg);
    return socket_recv_exit_common(ret, tid, args, cfg, stats_map, proto, func, fill_remote_hint);
}

SEC("kprobe/tcp_sendmsg")
int BPF_KPROBE(k_tcp_sendmsg, struct sock *sk, struct msghdr *msg, size_t size)
{
    __u32 cfg_key = 0;
    struct config *cfg = bpf_map_lookup_elem(&config_map, &cfg_key);
    return handle_sock_common(sk, size, IPPROTO_TCP, FUNC_TCP_SEND, true, cfg, select_stats_map(cfg), NULL, 0, 0);
}

SEC("kprobe/udp_sendmsg")
int BPF_KPROBE(k_udp_sendmsg, struct sock *sk, struct msghdr *msg, size_t len)
{
    __u32 cfg_key = 0;
    struct config *cfg = bpf_map_lookup_elem(&config_map, &cfg_key);
    struct flow_addr_hint hint = {};
    fill_addr_hint_from_msghdr(msg, &hint);
    return handle_sock_common(sk, len, IPPROTO_UDP, FUNC_UDP_SEND, true, cfg, select_stats_map(cfg), &hint, 0, 0);
}

SEC("kprobe/tcp_recvmsg")
int BPF_KPROBE(k_tcp_recvmsg_enter, struct sock *sk, struct msghdr *msg, size_t len, int flags, int addr_len)
{
    return socket_recv_enter(sk, msg);
}

SEC("kretprobe/tcp_recvmsg")
int BPF_KRETPROBE(k_tcp_recvmsg_exit)
{
    __s64 ret = (__s64)PT_REGS_RC(ctx);
    return socket_recv_exit_fixed(ret, IPPROTO_TCP, FUNC_TCP_RECV, false);
}

SEC("kprobe/udp_recvmsg")
int BPF_KPROBE(k_udp_recvmsg_enter, struct sock *sk, struct msghdr *msg, size_t len, int flags)
{
    return socket_recv_enter(sk, msg);
}

SEC("kretprobe/udp_recvmsg")
int BPF_KRETPROBE(k_udp_recvmsg_exit)
{
    __s64 ret = (__s64)PT_REGS_RC(ctx);
    return socket_recv_exit_fixed(ret, IPPROTO_UDP, FUNC_UDP_RECV, true);
}

char LICENSE[] SEC("license") = "GPL";
