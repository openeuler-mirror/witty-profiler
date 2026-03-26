#include "sysv_msg_dump.h"
#include <iostream>

void sysv_msg_dump_print_header()
{
    std::cout << "timestamp,pid,tid,msqid,direction,bytes,count,msg_type" << std::endl;
}

void sysv_msg_dump_emit(const sysv_msg_key &key, uint64_t window_start, 
                        uint64_t window_end, uint64_t bytes, uint64_t count,
                        int32_t msg_type)
{
    std::cout << window_end << ","
              << key.pid << ","
              << key.tid << ","
              << key.msqid << ","
              << (key.direction == 1 ? "send" : "recv") << ","
              << bytes << ","
              << count << ","
              << msg_type << std::endl;
}
