#pragma once

#include <linux/types.h>
#include <vector>

#include "pmu_version.h"

struct pmu_key {
    __u32 sccl_id;
    __u32 event_type;
    __u32 event_code;
    __u32 reserved;
};

struct pmu_value {
    __u64 count;
    __u64 first_ts;
    __u64 last_ts;
};

struct pmu_entry {
    pmu_key key;
    __u64 count;
    __u64 first_ts;
    __u64 last_ts;
};

void pmu_dump_print_header();
void pmu_dump_emit(const std::vector<pmu_entry> &entries, double interval_sec);

const char *pmu_dump_style();
int pmu_dump_style_id();
