#include "lru/lru_map.h"
#include "lru/lru_version.h"

#include <cstring>

bool lru_prepare(bpf_object *obj, int max_entries, int min_entries, LruState *state)
{
    (void)min_entries;
    if (!obj || !state)
        return false;

    std::memset(state, 0, sizeof(*state));
    state->dynamic = false;
    state->max_entries = max_entries;
    state->map_sizes[0] = max_entries;
    state->map_sizes[1] = max_entries;

    state->map_a = bpf_object__find_map_by_name(obj, "flow_stats_map_a");
    state->map_b = bpf_object__find_map_by_name(obj, "flow_stats_map_b");
    if (!state->map_a || !state->map_b)
        return false;

    if (max_entries > 0)
    {
        bpf_map__set_max_entries(state->map_a, max_entries);
        bpf_map__set_max_entries(state->map_b, max_entries);
    }

    return true;
}

bool lru_after_load(bpf_object *obj, LruState *state)
{
    (void)obj;
    if (!state || state->dynamic)
        return false;

    state->stats_fd_a = bpf_map__fd(state->map_a);
    state->stats_fd_b = bpf_map__fd(state->map_b);
    return state->stats_fd_a >= 0 && state->stats_fd_b >= 0;
}

int lru_read_fd(const LruState *state, int read_map)
{
    if (!state)
        return -1;
    return (read_map == 0) ? state->stats_fd_a : state->stats_fd_b;
}

int lru_maybe_resize(LruState *state, int read_map, int entry_cnt)
{
    (void)state;
    (void)read_map;
    (void)entry_cnt;
    return 0;
}

void lru_cleanup(LruState *state)
{
    (void)state;
}

const char *get_lru_style()
{
    return "fixed";
}

int get_lru_style_id()
{
    return LRU_STYLE_FIXED;
}
