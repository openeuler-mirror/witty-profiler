#ifndef PIPE_DUMP_H
#define PIPE_DUMP_H

#include <cstdint>

struct pipe_key {
    uint32_t pid;
    uint32_t tid;
    uint64_t inode;
    uint8_t  direction;
    uint8_t  is_fifo;
    uint8_t  padding[6];
};

struct pipe_stats {
    uint64_t start_ns;
    uint64_t end_ns;
    uint64_t bytes;
    uint64_t count;
};

void pipe_dump_print_header();
void pipe_dump_emit(const pipe_key &key, uint64_t window_start, uint64_t window_end,
                    uint64_t bytes, uint64_t count);

#endif
