#pragma once

#include <string>
#include "flow_types.h"

const char *flow_func_name(__u8 func_id);
std::string flow_ip_to_string(__u32 addr);

void flowdump_print_header();
void flowdump_emit(const flow_key &key,
                   __u64 window_start,
                   __u64 window_end,
                   __u64 bytes,
                   __u64 pkts);
