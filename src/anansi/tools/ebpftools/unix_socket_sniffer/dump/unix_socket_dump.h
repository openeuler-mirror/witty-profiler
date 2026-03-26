#ifndef UNIX_SOCKET_DUMP_H
#define UNIX_SOCKET_DUMP_H

#include <cstdint>

struct uds_key {
    uint32_t pid;
    uint32_t tid;
    uint64_t inode;
    uint8_t  socket_type;
    uint8_t  direction;
    uint8_t  padding[6];
};

struct uds_stats {
    uint64_t start_ns;
    uint64_t end_ns;
    uint64_t bytes;
    uint64_t count;
    uint32_t peer_inode;
    uint32_t padding;
};

void uds_dump_print_header();
void uds_dump_emit(const uds_key &key, uint64_t window_start,
                   uint64_t window_end, uint64_t bytes, uint64_t count,
                   uint32_t peer_inode);

#endif
