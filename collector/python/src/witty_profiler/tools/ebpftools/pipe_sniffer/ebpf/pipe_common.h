#ifndef PIPE_COMMON_H
#define PIPE_COMMON_H

#include "../ipc_common/ipc_common.h"
#include "../ipc_common/ipc_types.h"

struct pipe_key {
    __u32 pid;
    __u32 tid;
    __u64 inode;
    __u8  direction;
    __u8  is_fifo;
    __u8  padding[6];
};

struct pipe_stats {
    __u64 start_ns;
    __u64 end_ns;
    __u64 bytes;
    __u64 count;
};

struct pipe_args {
    __u64 inode;
    __u64 timestamp;
    __u8  direction;
    __u8  is_fifo;
    __u8  padding[6];
};

struct pipe_event {
    __u64 timestamp;
    __u32 pid;
    __u32 tid;
    __u64 inode;
    __u8  direction;
    __u8  is_fifo;
    __u8  padding[6];
    __u64 bytes;
};

#endif
