#ifndef UNIX_SOCKET_COMMON_H
#define UNIX_SOCKET_COMMON_H

#include "../ipc_common/ipc_common.h"
#include "../ipc_common/ipc_types.h"

struct uds_key {
    __u32 pid;
    __u32 tid;
    __u64 inode;
    __u8  socket_type;
    __u8  direction;
    __u8  padding[6];
};

struct uds_stats {
    __u64 start_ns;
    __u64 end_ns;
    __u64 bytes;
    __u64 count;
    __u32 peer_inode;
    __u32 padding;
};

struct uds_args {
    __u64 inode;
    __u64 peer_inode;
    __u64 timestamp;
    __u8  socket_type;
    __u8  padding[7];
};

#endif
