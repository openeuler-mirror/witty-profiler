#pragma once

#include <linux/types.h>
#include <vector>

#include "sched_version.h"

struct sched_key {
    __u32 pid;
    __u32 tgid;
    __u32 cpu;
};

struct sched_entry {
    sched_key key;
    __u64 time_ns;
};

void sched_dump_print_header();
void sched_dump_emit(const std::vector<sched_entry> &entries);

const char *sched_dump_style();
int sched_dump_style_id();
