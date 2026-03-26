#ifndef IPC_TYPES_H
#define IPC_TYPES_H

enum ipc_type {
    IPC_TYPE_PIPE        = 1,
    IPC_TYPE_FIFO        = 2,
    IPC_TYPE_SYSV_MSG    = 3,
    IPC_TYPE_POSIX_MQ    = 4,
    IPC_TYPE_SYSV_SEM    = 5,
};

enum ipc_direction {
    IPC_DIR_WRITE = 1,
    IPC_DIR_READ  = 2,
};

enum ipc_op_type {
    IPC_OP_DATA     = 1,
    IPC_OP_OPEN     = 2,
    IPC_OP_CLOSE    = 3,
    IPC_OP_CONTROL  = 4,
};

#endif
