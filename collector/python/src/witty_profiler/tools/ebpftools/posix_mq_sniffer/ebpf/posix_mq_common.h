#ifndef POSIX_MQ_COMMON_H
#define POSIX_MQ_COMMON_H

#include "../ipc_common/ipc_common.h"
#include "../ipc_common/ipc_types.h"

struct posix_mq_key {
    __u32 pid;
    __u32 tid;
    __u32 mqd;
    __u8  direction;
    __u8  padding[3];
};

struct posix_mq_stats {
    __u64 start_ns;
    __u64 end_ns;
    __u64 bytes;
    __u64 count;
    __u32 msg_prio;
    __u32 padding;
};

struct posix_mq_args {
    __u32 mqd;
    __u32 msg_prio;
    __u64 timestamp;
    __u64 msg_len;
};

#endif
