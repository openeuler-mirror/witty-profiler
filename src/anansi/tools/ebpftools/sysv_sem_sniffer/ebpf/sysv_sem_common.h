#ifndef SYSV_SEM_COMMON_H
#define SYSV_SEM_COMMON_H

#include "../ipc_common/ipc_common.h"
#include "../ipc_common/ipc_types.h"

struct sysv_sem_key {
    __u32 pid;
    __u32 tid;
    __u32 semid;
    __u16 sem_num;
    __u16 sem_op_type;
};

struct sysv_sem_stats {
    __u64 start_ns;
    __u64 end_ns;
    __u64 count;
    __s16 sem_op_val;
    __u16 sem_flg;
    __u32 padding;
};

struct sysv_sem_args {
    __u64 timestamp;
    __u32 semid;
    __u16 sem_num;
    __s16 sem_op;
    __u16 sem_flg;
    __u16 padding1;
    __u32 padding2;
};

struct sembuf_user {
    __u16 sem_num;
    __s16 sem_op;
    __s16 sem_flg;
};

#endif
