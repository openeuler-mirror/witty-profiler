#include "flowdump/flowdump.h"
#include "flowdump/flow_dump_version.h"

#include <iostream>

void flowdump_print_header()
{
    std::cout << "function, local_pid, local_tid, local_addr, local_port, remote_addr, remote_port, start_time, end_time, data_size_total, packet_cnt" << std::endl;
}

void flowdump_emit(const flow_key &key,
                   __u64 window_start,
                   __u64 window_end,
                   __u64 bytes,
                   __u64 pkts)
{
    std::cout << flow_func_name(key.func_id)
              << "," << key.pid
              << "," << key.tid
              << "," << flow_ip_to_string(key.saddr)
              << "," << key.sport
              << "," << flow_ip_to_string(key.daddr)
              << "," << key.dport
              << "," << window_start
              << "," << window_end
              << "," << bytes
              << "," << pkts
              << std::endl;
}

const char *flow_dump_style()
{
    return "csv";
}

int flow_dump_style_id()
{
    return FLOW_DUMP_STYLE_CSV;
}
