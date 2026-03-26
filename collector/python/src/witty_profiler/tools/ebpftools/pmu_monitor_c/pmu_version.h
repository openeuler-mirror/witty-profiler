#pragma once

#ifdef __VMLINUX_H__
typedef __u32 pmu_u32;
#else
#include <stdint.h>
typedef uint32_t pmu_u32;
#endif

enum pmu_output_style {
    PMU_OUTPUT_CSV     = 0,
    PMU_OUTPUT_MSGSPEC = 1,
};

struct pmu_version {
    pmu_u32 output_style;
    pmu_u32 reserved;
};
