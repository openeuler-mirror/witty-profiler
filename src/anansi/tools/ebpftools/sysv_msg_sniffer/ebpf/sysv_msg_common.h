#ifndef SYSV_MSG_COMMON_H
#define SYSV_MSG_COMMON_H

#include "../ipc_common/ipc_common.h"
#include "../ipc_common/ipc_types.h"

struct sysv_msg_key {
    __u32 pid;
    __u32 tid;
    __u32 msqid;
    __u8  direction;
    __u8  padding[3];
};

struct sysv_msg_stats {
    __u64 start_ns;
    __u64 end_ns;
    __u64 bytes;
    __u64 count;
    __s32 msg_type;
    __u32 padding;
};

struct sysv_msg_args {
    __u32 msqid;
    __s32 msg_type;
    __u64 timestamp;
    __u64 msgsz;
};

#endif
