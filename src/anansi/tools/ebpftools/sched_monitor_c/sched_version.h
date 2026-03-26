#pragma once

#ifdef __VMLINUX_H__
typedef __u32 sched_u32;
#else
#include <stdint.h>
typedef uint32_t sched_u32;
#endif

enum sched_output_style {
    SCHED_OUTPUT_CSV = 0,
    SCHED_OUTPUT_MSGSPEC = 1,
};

struct sched_version {
    sched_u32 output_style;
    sched_u32 reserved;
};
