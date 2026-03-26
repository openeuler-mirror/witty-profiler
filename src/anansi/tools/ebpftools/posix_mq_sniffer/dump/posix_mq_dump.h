#ifndef POSIX_MQ_DUMP_H
#define POSIX_MQ_DUMP_H

#include <cstdint>

struct posix_mq_key {
    uint32_t pid;
    uint32_t tid;
    uint32_t mqd;
    uint8_t  direction;
    uint8_t  padding[3];
};

struct posix_mq_stats {
    uint64_t start_ns;
    uint64_t end_ns;
    uint64_t bytes;
    uint64_t count;
    uint32_t msg_prio;
};

void posix_mq_dump_print_header();
void posix_mq_dump_emit(const posix_mq_key &key, uint64_t window_start,
                        uint64_t window_end, uint64_t bytes, uint64_t count,
                        uint32_t msg_prio);

#endif
