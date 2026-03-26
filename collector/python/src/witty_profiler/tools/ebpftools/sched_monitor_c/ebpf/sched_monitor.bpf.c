#include "vmlinux.h"
#include "sched_version.h"

#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>

struct sched_config {
    __u32 tgid_filter_enabled;
    __u32 pid_filter_enabled;
    __u32 cpu_filter_enabled;
    __u8 active_map;
    __u8 reserved1;
    __u16 reserved2;
};

struct sched_key {
    __u32 pid;
    __u32 tgid;
    __u32 cpu;
};

struct cpu_state {
    __u64 start_ts;
    __u32 pid;
    __u32 reserved;
};

struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, 1);
    __type(key, __u32);
    __type(value, struct sched_config);
} config_map SEC(".maps");

struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 65535);
    __type(key, __u32);
    __type(value, __u8);
} allowed_tgid_map SEC(".maps");

struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 65535);
    __type(key, __u32);
    __type(value, __u8);
} allowed_pid_map SEC(".maps");

struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 1024);
    __type(key, __u32);
    __type(value, __u8);
} allowed_cpu_map SEC(".maps");

struct {
    __uint(type, BPF_MAP_TYPE_PERCPU_ARRAY);
    __uint(max_entries, 1);
    __type(key, __u32);
    __type(value, struct cpu_state);
} current_state_map SEC(".maps");

struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 262144);
    __type(key, struct sched_key);
    __type(value, __u64);
} stats_map0 SEC(".maps");

struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 262144);
    __type(key, struct sched_key);
    __type(value, __u64);
} stats_map1 SEC(".maps");

const volatile struct sched_version sched_ver = {
#ifdef SCHED_OUTPUT_MSGSPEC
    .output_style = SCHED_OUTPUT_MSGSPEC,
#else
    .output_style = SCHED_OUTPUT_CSV,
#endif
    .reserved = 0,
};

static __always_inline bool map_contains(void *map, __u32 key)
{
    __u8 *val = bpf_map_lookup_elem(map, &key);
    return val != NULL;
}

static __always_inline bool pass_filters(const struct sched_config *cfg, __u32 tgid, __u32 pid, __u32 cpu)
{
    if (cfg->tgid_filter_enabled && !map_contains(&allowed_tgid_map, tgid))
        return false;
    if (cfg->pid_filter_enabled && !map_contains(&allowed_pid_map, pid))
        return false;
    if (cfg->cpu_filter_enabled && !map_contains(&allowed_cpu_map, cpu))
        return false;
    return true;
}

SEC("tp/sched/sched_switch")
int handle_sched_switch(struct trace_event_raw_sched_switch *ctx)
{
    __u32 cfg_key = 0;
    struct sched_config *cfg = bpf_map_lookup_elem(&config_map, &cfg_key);
    if (!cfg)
        return 0;

    __u64 now = bpf_ktime_get_ns();
    __u32 cpu = bpf_get_smp_processor_id();

    __u32 state_key = 0;
    struct cpu_state *state = bpf_map_lookup_elem(&current_state_map, &state_key);
    if (!state)
        return 0;

    __u32 prev_pid = ctx->prev_pid;
    if (state->start_ts != 0 && state->pid == prev_pid)
    {
        __u64 delta = now - state->start_ts;
        __u64 pid_tgid = bpf_get_current_pid_tgid();
        __u32 tgid = pid_tgid >> 32;
        if (pass_filters(cfg, tgid, prev_pid, cpu))
        {
            struct sched_key key = {
                .pid = prev_pid,
                .tgid = tgid,
                .cpu = cpu,
            };
            __u64 *acc = NULL;
            if (cfg->active_map)
            {
                acc = bpf_map_lookup_elem(&stats_map1, &key);
                if (!acc)
                {
                    __u64 zero = 0;
                    bpf_map_update_elem(&stats_map1, &key, &zero, BPF_NOEXIST);
                    acc = bpf_map_lookup_elem(&stats_map1, &key);
                }
            }
            else
            {
                acc = bpf_map_lookup_elem(&stats_map0, &key);
                if (!acc)
                {
                    __u64 zero = 0;
                    bpf_map_update_elem(&stats_map0, &key, &zero, BPF_NOEXIST);
                    acc = bpf_map_lookup_elem(&stats_map0, &key);
                }
            }
            if (acc)
                *acc += delta;
        }
    }

    __u32 next_pid = ctx->next_pid;
    if (next_pid == 0)
    {
        state->start_ts = 0;
        state->pid = 0;
        return 0;
    }

    state->start_ts = now;
    state->pid = next_pid;

    return 0;
}

char LICENSE[] SEC("license") = "Dual BSD/GPL";
