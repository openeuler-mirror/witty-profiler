#pragma once

#include <linux/types.h>
#include <vector>

#include "cache_miss_version.h"

struct cache_miss_key {
    __u32 tgid;
    __u32 pid;
    __u32 cpu;
};

struct cache_miss_value {
    __u64 l1i;
    __u64 llc;
};

struct cache_miss_entry {
    cache_miss_key key;
    __u64 l1i;
    __u64 llc;
};

void cache_miss_dump_print_header();
void cache_miss_dump_emit(const std::vector<cache_miss_entry> &entries);

const char *cache_miss_dump_style();
int cache_miss_dump_style_id();
