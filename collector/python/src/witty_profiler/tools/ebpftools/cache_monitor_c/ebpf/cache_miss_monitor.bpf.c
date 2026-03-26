#include "vmlinux.h"
#include "cache_miss_version.h"

#include <bpf/bpf_helpers.h>

struct cache_miss_config {
    __u32 pid;
    __u32 tid;
    __u32 cpu;
    __u8 active_map;
    __u8 reserved1;
    __u16 reserved2;
};

struct cache_miss_key {
    __u32 tgid;
    __u32 pid;
    __u32 cpu;
};

struct cache_miss_value {
    __u64 l1i;
    __u64 llc;
};

struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, 1);
    __type(key, __u32);
    __type(value, struct cache_miss_config);
} config_map SEC(".maps");

#ifndef CACHE_MAX_ENTRIES
#define CACHE_MAX_ENTRIES 65535
#endif

struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, CACHE_MAX_ENTRIES);
    __type(key, struct cache_miss_key);
    __type(value, struct cache_miss_value);
} count_map0 SEC(".maps");

struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, CACHE_MAX_ENTRIES);
    __type(key, struct cache_miss_key);
    __type(value, struct cache_miss_value);
} count_map1 SEC(".maps");

struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, 1);
    __type(key, __u32);
    __type(value, __u64);
} drop_count_map SEC(".maps");

const volatile struct cache_miss_version cache_miss_ver = {
#ifdef CACHE_OUTPUT_MSGSPEC
    .output_style = CACHE_MISS_OUTPUT_MSGSPEC,
#else
    .output_style = CACHE_MISS_OUTPUT_CSV,
#endif
    .reserved = 0,
};

static __always_inline int handle_cache_miss(struct bpf_perf_event_data *ctx, bool is_l1i)
{
    __u32 key = 0;
    struct cache_miss_config *cfg = bpf_map_lookup_elem(&config_map, &key);
    if (!cfg)
        return 0;

    __u64 pid_tgid = bpf_get_current_pid_tgid();
    __u32 tgid = pid_tgid >> 32;
    __u32 pid = (__u32)pid_tgid;

    if (cfg->pid && tgid != cfg->pid)
        return 0;
    if (cfg->tid && pid != cfg->tid)
        return 0;
    __u32 cpu = bpf_get_smp_processor_id();
    if (cfg->cpu != 0xFFFFFFFF && cfg->cpu != cpu)
        return 0;

    struct cache_miss_key stats_key = {
        .tgid = tgid,
        .pid = pid,
        .cpu = cpu,
    };

    void *map_ptr = &count_map0;
    if (cfg->active_map)
        map_ptr = &count_map1;

    struct cache_miss_value *counter = bpf_map_lookup_elem(map_ptr, &stats_key);
    if (!counter)
    {
        struct cache_miss_value zero = {};
        if (bpf_map_update_elem(map_ptr, &stats_key, &zero, BPF_NOEXIST) != 0)
        {
            __u32 drop_key = 0;
            __u64 *drops = bpf_map_lookup_elem(&drop_count_map, &drop_key);
            if (drops)
                __sync_fetch_and_add(drops, 1);
            return 0;
        }
        counter = bpf_map_lookup_elem(map_ptr, &stats_key);
    }

    if (counter)
    {
        if (is_l1i)
            __sync_fetch_and_add(&counter->l1i, 1);
        else
            __sync_fetch_and_add(&counter->llc, 1);
    }

    return 0;
}

SEC("perf_event")
int handle_l1i_miss(struct bpf_perf_event_data *ctx)
{
    return handle_cache_miss(ctx, true);
}

SEC("perf_event")
int handle_llc_miss(struct bpf_perf_event_data *ctx)
{
    return handle_cache_miss(ctx, false);
}

char LICENSE[] SEC("license") = "Dual BSD/GPL";
