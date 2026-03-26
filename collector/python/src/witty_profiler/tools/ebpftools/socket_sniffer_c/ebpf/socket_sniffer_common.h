#ifndef SOCKET_SNIFFER_COMMON_H
#define SOCKET_SNIFFER_COMMON_H

#include "vmlinux.h"

#include <bpf/bpf_helpers.h>
#include <bpf/bpf_endian.h>
#include <bpf/bpf_tracing.h>
#include <bpf/bpf_core_read.h>
#include <stdbool.h>

#ifndef NULL
#define NULL ((void *)0)
#endif

#ifndef AF_INET
#define AF_INET 2
#endif
#ifndef IPPROTO_TCP
#define IPPROTO_TCP 6
#endif
#ifndef IPPROTO_UDP
#define IPPROTO_UDP 17
#endif

enum func_id
{
    FUNC_TCP_SEND = 1,
    FUNC_UDP_SEND = 2,
    FUNC_TCP_RECV = 3,
    FUNC_UDP_RECV = 4,
};

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

struct flow_addr_hint
{
    __u32 saddr;
    __u32 daddr;
    __u16 sport;
    __u16 dport;
    __u8 has_saddr;
    __u8 has_daddr;
    __u8 has_sport;
    __u8 has_dport;
};

struct recv_args
{
    struct sock *sk;
    struct msghdr *msg;
    void *msg_name;
    __u64 msg_namelen;
    __u32 pid;
    __u32 tid;
};

/* recv args map declaration for helpers */
struct recv_args_map_def
{
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 8192);
    __type(key, __u32);
    __type(value, struct recv_args);
};

extern struct recv_args_map_def recv_args_map;

static __always_inline void load_msg_name_len(struct msghdr *msg, void **msg_name, __u64 *msg_namelen)
{
    if (!msg)
        return;

    void *name = NULL;
    __u64 len = 0;

    if (msg_name)
    {
        /* try kernel copy first, then user-space */
        if (bpf_probe_read_kernel(&name, sizeof(name), &msg->msg_name) != 0)
            bpf_probe_read_user(&name, sizeof(name), &msg->msg_name);
        *msg_name = name;
    }

    if (msg_namelen)
    {
        if (bpf_probe_read_kernel(&len, sizeof(len), &msg->msg_namelen) != 0)
            bpf_probe_read_user(&len, sizeof(len), &msg->msg_namelen);
        *msg_namelen = len;
    }
}

static __always_inline int socket_recv_enter(struct sock *sk, struct msghdr *msg)
{
    __u64 pid_tgid = bpf_get_current_pid_tgid();
    __u32 tid = (__u32)pid_tgid;
    __u32 pid = (__u32)(pid_tgid >> 32);
    struct recv_args args = { .sk = sk, .msg = msg, .pid = pid, .tid = tid };
    load_msg_name_len(msg, &args.msg_name, &args.msg_namelen);
    bpf_map_update_elem(&recv_args_map, &tid, &args, BPF_ANY);
    return 0;
}

/**
 * @brief 从内核或用户空间读取sockaddr_in结构体数据
 * 
 * 该函数尝试从指定源地址读取sockaddr_in结构体数据到目标缓冲区，
 * 首先尝试从内核空间读取，如果失败则尝试从用户空间读取
 * 
 * @param src 源地址指针，指向要读取的sockaddr_in数据
 * @param dst 目标指针，用于存储读取到的sockaddr_in结构体数据
 * @return int 成功返回0，失败返回-1
 */
static __always_inline int read_sockaddr_in(void *src, struct sockaddr_in *dst)
{
    if (!src || !dst)
        return -1;

    // 尝试从内核空间读取数据
    if (bpf_probe_read_kernel(dst, sizeof(*dst), src) == 0)
        return 0;

    // 内核空间读取失败后，尝试从用户空间读取数据
    if (bpf_probe_read_user(dst, sizeof(*dst), src) == 0)
        return 0;

    return -1;
}

/**
 * @brief 从msghdr结构体中提取地址信息并填充到flow_addr_hint结构体中
 * 
 * 该函数解析传入的消息头结构体，从中读取目标地址和端口信息，
 * 并将其存储到flow_addr_hint结构体中用于后续的流量分析或处理。
 * 
 * @param msg 指向msghdr结构体的指针，包含消息的目标地址信息
 * @param hint 指向flow_addr_hint结构体的指针，用于存储提取的地址提示信息
 * @return 无返回值
 */
static __always_inline void fill_addr_hint_from_sockaddr_send(void *msg_name, __u64 name_len, struct flow_addr_hint *hint)
{
    if (!msg_name || !hint)
        return;

    if (name_len < sizeof(struct sockaddr_in))
        return;

    // 读取sockaddr_in结构体中的地址信息
    struct sockaddr_in addr = {};
    if (read_sockaddr_in(msg_name, &addr) != 0)
        return;

    if (addr.sin_family != AF_INET)
        return;

    // 填充目标地址信息到hint结构体
    hint->has_daddr = 1;
    hint->daddr = addr.sin_addr.s_addr;
    hint->has_dport = 1;
    hint->dport = bpf_ntohs(addr.sin_port);
}

// 用于recv方向，从用户缓冲区读取来源地址和端口（远端）
static __always_inline void fill_addr_hint_from_sockaddr_recv(void *msg_name, __u64 name_len, struct flow_addr_hint *hint)
{
    if (!msg_name || !hint)
        return;

    if (name_len < sizeof(struct sockaddr_in))
        return;

    struct sockaddr_in addr = {};
    if (read_sockaddr_in(msg_name, &addr) != 0)
        return;

    if (addr.sin_family != AF_INET)
        return;

    // 对端地址/端口 -> 覆盖 flow_key 的 daddr/dport（remote_*）
    hint->has_daddr = 1;
    hint->daddr = addr.sin_addr.s_addr;
    hint->has_dport = 1;
    hint->dport = bpf_ntohs(addr.sin_port);
}

static __always_inline void fill_addr_hint_from_msghdr(struct msghdr *msg, struct flow_addr_hint *hint)
{
    if (!msg || !hint)
        return;

    void *msg_name = NULL;
    __u64 name_len = 0;
    load_msg_name_len(msg, &msg_name, &name_len);
    fill_addr_hint_from_sockaddr_send(msg_name, name_len, hint);
}

static __always_inline int update_stats(void *map, const struct flow_key *key, __u64 bytes, __u64 now)
{
    struct flow_stats_val *stats = bpf_map_lookup_elem(map, key);
    if (!stats)
    {
        struct flow_stats_val init = {
            .start_ns = now,
            .end_ns = now,
            .bytes = bytes,
            .pkts = 1,
        };
        bpf_map_update_elem(map, key, &init, BPF_ANY);
    }
    else
    {
        stats->bytes += bytes;
        stats->end_ns = now;
        stats->pkts += 1;
    }

    return 0;
}

/**
 * @brief 处理套接字通用逻辑，收集网络流量统计信息
 * 
 * @param sk 套接字结构指针
 * @param bytes 传输的字节数
 * @param proto 协议类型
 * @param func 函数标识符
 * @param is_send 是否为发送操作
 * @param cfg 配置结构指针
 * @param map 统计数据存储映射
 * @param hint 流量地址提示信息
 * @param pid_override 可选PID覆盖，0表示使用当前PID
 * @param tid_override 可选TID覆盖，0表示使用当前TID
 * @return int 返回处理结果，成功返回更新统计的结果，失败返回0
 */
static __always_inline int handle_sock_common(struct sock *sk,
                                              __u64 bytes,
                                              __u8 proto,
                                              __u8 func,
                                              bool is_send,
                                              struct config *cfg,
                                              void *map,
                                              const struct flow_addr_hint *hint,
                                              __u32 pid_override,
                                              __u32 tid_override)
{
    if (!sk || !bytes || !map)
        return 0;

    __u32 pid, tid;
    if (pid_override && tid_override)
    {
        pid = pid_override;
        tid = tid_override;
    }
    else
    {
        __u64 pid_tgid = bpf_get_current_pid_tgid();
        pid = (__u32)(pid_tgid >> 32);
        tid = (__u32)pid_tgid;
    }
    
    // 检查配置过滤条件
    if (cfg)
    {
        if (cfg->target_pid && cfg->target_pid != pid)
            return 0;
        if (is_send && !cfg->enable_send)
            return 0;
        if (!is_send && !cfg->enable_recv)
            return 0;
    }

    __u16 family = BPF_CORE_READ(sk, __sk_common.skc_family);
    if (family != AF_INET)
        return 0;

    __u32 saddr = BPF_CORE_READ(sk, __sk_common.skc_rcv_saddr);
    __u32 daddr = BPF_CORE_READ(sk, __sk_common.skc_daddr);

    struct inet_sock *inet = (struct inet_sock *)sk;
    __u16 sport = bpf_ntohs(BPF_CORE_READ(inet, inet_sport));
    __u16 dport = bpf_ntohs(BPF_CORE_READ(sk, __sk_common.skc_dport));

    // 根据提示信息更新地址和端口信息
    if (hint)
    {
        if (hint->has_saddr)
            saddr = hint->saddr;
        if (hint->has_daddr)
            daddr = hint->daddr;
        if (hint->has_sport)
            sport = hint->sport;
        if (hint->has_dport)
            dport = hint->dport;
    }
    
    // 对于UDP接收，我们更关注的是本地监听端口(sport)的存在
    if (!sport)
        return 0;
        
    // 对于UDP接收操作，即使dport为0也可以接受
    // 因为UDP接收时，目标端口就是本地监听端口(sport)，而源端口应该从其他途径获取
    if (is_send && !dport)
        return 0;


    // 如果是send，那么不需要记录saddr/sport，因为是本地地址且端口会动态变化
    // 从而实现将同一进程线程发送往同一对端地址端口的流量进行合并（key相同）
    if (cfg && cfg->compress_msg)
    {
        if (is_send)
        {
            saddr = 0;
            sport = 0;
            tid = 0;
        }
    }

    struct flow_key key = {};
    key.pid = pid;
    key.tid = tid;
    key.proto = proto;
    key.func_id = func;
    key.saddr = saddr;
    key.daddr = daddr;
    key.sport = sport;
    key.dport = dport;

    

    __u64 now = bpf_ktime_get_ns();
    return update_stats(map, &key, bytes, now);
}

static __always_inline int socket_recv_exit_common(__s64 ret,
                                                   __u32 tid,
                                                   struct recv_args *args,
                                                   struct config *cfg,
                                                   void *stats_map,
                                                   __u8 proto,
                                                   __u8 func,
                                                   bool fill_remote_hint)
{
    if (!args)
    {
        if (ret <= 0)
            return 0;
        return 0;
    }

    if (ret > 0)
    {
        struct flow_addr_hint hint = {};
        struct flow_addr_hint *hint_ptr = NULL;
        if (fill_remote_hint)
        {
            fill_addr_hint_from_sockaddr_recv(args->msg_name, args->msg_namelen, &hint);
            hint_ptr = &hint;
        }
        handle_sock_common(args->sk, ret, proto, func, false, cfg, stats_map, hint_ptr, args->pid, args->tid);
    }
    bpf_map_delete_elem(&recv_args_map, &tid);
    return 0;
}

#endif
