#include "lru/lru_map.h"
#include "lru/lru_version.h"

#include "flow_types.h"

#include <bpf/bpf.h>
#include <unistd.h>
#include <cstring>
#include <iostream>

static int create_stats_map(int entries)
{
    if (entries < 1)
        entries = 1;
    std::clog << "create_stats_map with entries=" << entries << std::endl;
    LIBBPF_OPTS(bpf_map_create_opts, opts);
    return bpf_map_create(BPF_MAP_TYPE_LRU_PERCPU_HASH,
                          "flow_stats_inner",
                          sizeof(flow_key),
                          sizeof(flow_stats_val),
                          entries,
                          &opts);
}

bool lru_prepare(bpf_object *obj, int max_entries, int min_entries, LruState *state)
{
    if (!obj || !state)
        return false;

    std::memset(state, 0, sizeof(*state));
    state->dynamic = true;
    state->max_entries = max_entries;
    state->min_entries = min_entries;
    state->map_fds[0] = -1;
    state->map_fds[1] = -1;
    state->map_sizes[0] = max_entries;
    state->map_sizes[1] = max_entries;

    state->map_outer = bpf_object__find_map_by_name(obj, "flow_stats_maps");
    if (!state->map_outer)
        return false;

    state->map_fds[0] = create_stats_map(max_entries);
    if (state->map_fds[0] < 0)
        return false;

    state->map_fds[1] = create_stats_map(max_entries);
    if (state->map_fds[1] < 0)
    {
        close(state->map_fds[0]);
        state->map_fds[0] = -1;
        return false;
    }

    if (bpf_map__set_inner_map_fd(state->map_outer, state->map_fds[0]) != 0)
    {
        close(state->map_fds[0]);
        close(state->map_fds[1]);
        state->map_fds[0] = -1;
        state->map_fds[1] = -1;
        return false;
    }

    return true;
}

bool lru_after_load(bpf_object *obj, LruState *state)
{
    (void)obj;
    if (!state || !state->dynamic)
        return false;

    state->stats_outer_fd = bpf_map__fd(state->map_outer);
    if (state->stats_outer_fd < 0)
        return false;

    __u32 idx0 = 0;
    __u32 idx1 = 1;
    if (bpf_map_update_elem(state->stats_outer_fd, &idx0, &state->map_fds[0], BPF_ANY) != 0 ||
        bpf_map_update_elem(state->stats_outer_fd, &idx1, &state->map_fds[1], BPF_ANY) != 0)
    {
        return false;
    }

    return true;
}

int lru_read_fd(const LruState *state, int read_map)
{
    if (!state)
        return -1;
    return state->map_fds[read_map];
}

int lru_maybe_resize(LruState *state, int read_map, int entry_cnt)
{
    if (!state || !state->dynamic)
        return 0;

    int map_size = state->map_sizes[read_map];

    if (entry_cnt < (map_size >> 3))
        map_size >>= 1;
    if (entry_cnt >= (map_size >> 1))
    {
        map_size <<= 1;
        if (map_size > state->max_entries)
            map_size = state->max_entries;
    }
    if (map_size < state->min_entries)
        map_size = state->min_entries;

    if (map_size == state->map_sizes[read_map])
        return 0;

    int new_fd = create_stats_map(map_size);
    if (new_fd < 0)
        return 0;

    __u32 map_idx = static_cast<__u32>(read_map);
    if (bpf_map_update_elem(state->stats_outer_fd, &map_idx, &new_fd, BPF_ANY) != 0)
    {
        close(new_fd);
        return 0;
    }

    close(state->map_fds[read_map]);
    state->map_fds[read_map] = new_fd;
    state->map_sizes[read_map] = map_size;
    return 1;
}

void lru_cleanup(LruState *state)
{
    if (!state || !state->dynamic)
        return;

    if (state->map_fds[0] >= 0)
        close(state->map_fds[0]);
    if (state->map_fds[1] >= 0)
        close(state->map_fds[1]);
}

const char *get_lru_style()
{
    return "dynamic";
}

int get_lru_style_id()
{
    return LRU_STYLE_DYNAMIC;
}
