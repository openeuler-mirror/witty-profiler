#include "unix_socket_dump.h"
#include <iostream>

void uds_dump_print_header()
{
    std::cout << "timestamp,pid,tid,inode,socket_type,direction,bytes,count,peer_inode" << std::endl;
}

void uds_dump_emit(const uds_key &key, uint64_t window_start,
                   uint64_t window_end, uint64_t bytes, uint64_t count,
                   uint32_t peer_inode)
{
    const char *sock_type_str = "unknown";
    if (key.socket_type == 1)
        sock_type_str = "stream";
    else if (key.socket_type == 2)
        sock_type_str = "dgram";
    
    std::cout << window_end << ","
              << key.pid << ","
              << key.tid << ","
              << key.inode << ","
              << sock_type_str << ","
              << (key.direction == 1 ? "send" : "recv") << ","
              << bytes << ","
              << count << ","
              << peer_inode << std::endl;
}
