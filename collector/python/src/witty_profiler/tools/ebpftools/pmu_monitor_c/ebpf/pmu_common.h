#pragma once

#ifdef __VMLINUX_H__
#else
#include <linux/types.h>
#endif

enum hccs_event_type {
    EVENT_DDR = 0,
    EVENT_HHA = 1,
    EVENT_L3C = 2,
    EVENT_PA  = 3,
    EVENT_MAX = 4,
};

/* Aggregation key: SCCL-level, not per-device, to reduce map entries */
struct pmu_key {
    __u32 sccl_id;
    __u32 event_type;    /* hccs_event_type */
    __u32 event_code;    /* raw PMU event code (e.g. 0x83) */
    __u32 reserved;
};

struct pmu_value {
    __u64 count;
    __u64 first_ts;      /* ns */
    __u64 last_ts;       /* ns */
};

struct pmu_config {
    __u32 target_sccl;   /* 0xFFFFFFFF = all */
    __u8  active_map;    /* double-buffer: 0 or 1 */
    __u8  enable_ddr;
    __u8  enable_hha;
    __u8  enable_l3c;
    __u8  enable_pa;
    __u8  reserved[3];
};

/* max_SCCLs(16) * EVENT_MAX(4) * ~16 codes = 1024; 2048 for headroom */
#ifndef PMU_MAX_ENTRIES
#define PMU_MAX_ENTRIES 2048
#endif
