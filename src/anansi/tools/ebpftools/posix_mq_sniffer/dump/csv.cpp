#include "posix_mq_dump.h"
#include <iostream>

void posix_mq_dump_print_header()
{
    std::cout << "timestamp,pid,tid,mqd,direction,bytes,count,msg_prio" << std::endl;
}

void posix_mq_dump_emit(const posix_mq_key &key, uint64_t window_start,
                        uint64_t window_end, uint64_t bytes, uint64_t count,
                        uint32_t msg_prio)
{
    std::cout << window_end << ","
              << key.pid << ","
              << key.tid << ","
              << key.mqd << ","
              << (key.direction == 1 ? "send" : "recv") << ","
              << bytes << ","
              << count << ","
              << msg_prio << std::endl;
}
