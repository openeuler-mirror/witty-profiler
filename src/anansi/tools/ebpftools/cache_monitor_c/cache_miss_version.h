#pragma once

#ifdef __VMLINUX_H__
typedef __u32 cache_miss_u32;
#else
#include <stdint.h>
typedef uint32_t cache_miss_u32;
#endif

enum cache_miss_output_style {
    CACHE_MISS_OUTPUT_CSV = 0,
    CACHE_MISS_OUTPUT_MSGSPEC = 1,
};

struct cache_miss_version {
    cache_miss_u32 output_style;
    cache_miss_u32 reserved;
};
