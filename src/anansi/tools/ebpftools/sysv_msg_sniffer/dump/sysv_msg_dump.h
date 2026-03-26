#ifndef SYSV_MSG_DUMP_H
#define SYSV_MSG_DUMP_H

#include <cstdint>

struct sysv_msg_key {
    uint32_t pid;
    uint32_t tid;
    uint32_t msqid;
    uint8_t  direction;
    uint8_t  padding[3];
};

struct sysv_msg_stats {
    uint64_t start_ns;
    uint64_t end_ns;
    uint64_t bytes;
    uint64_t count;
    int32_t  msg_type;
};

void sysv_msg_dump_print_header();
void sysv_msg_dump_emit(const sysv_msg_key &key, uint64_t window_start, 
                        uint64_t window_end, uint64_t bytes, uint64_t count,
                        int32_t msg_type);

#endif
