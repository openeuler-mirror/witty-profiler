#include "pipe_dump.h"
#include <iostream>
#include <iomanip>

void pipe_dump_print_header()
{
    std::cout << "timestamp,pid,tid,inode,direction,is_fifo,bytes,count" << std::endl;
}

void pipe_dump_emit(const pipe_key &key, uint64_t window_start, uint64_t window_end,
                    uint64_t bytes, uint64_t count)
{
    std::cout << window_end << ","
              << key.pid << ","
              << key.tid << ","
              << key.inode << ","
              << (key.direction == 1 ? "write" : "read") << ","
              << static_cast<int>(key.is_fifo) << ","
              << bytes << ","
              << count << std::endl;
}
