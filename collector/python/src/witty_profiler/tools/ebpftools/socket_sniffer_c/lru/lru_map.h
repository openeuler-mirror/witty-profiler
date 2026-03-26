#pragma once

#include <bpf/libbpf.h>

struct LruState
{
    bool dynamic;
    int stats_fd_a;
    int stats_fd_b;
    int stats_outer_fd;
    int map_fds[2];
    int map_sizes[2];
    int max_entries;
    int min_entries;
    bpf_map *map_a;
    bpf_map *map_b;
    bpf_map *map_outer;
};

bool lru_prepare(bpf_object *obj, int max_entries, int min_entries, LruState *state);
bool lru_after_load(bpf_object *obj, LruState *state);
int lru_read_fd(const LruState *state, int read_map);
int lru_maybe_resize(LruState *state, int read_map, int entry_cnt);
void lru_cleanup(LruState *state);
