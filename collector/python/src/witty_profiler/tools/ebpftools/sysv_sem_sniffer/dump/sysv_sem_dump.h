#ifndef SYSV_SEM_DUMP_H
#define SYSV_SEM_DUMP_H

#include <cstdint>

struct sysv_sem_key {
    uint32_t pid;
    uint32_t tid;
    uint32_t semid;
    uint16_t sem_num;
    uint16_t sem_op_type;
};

struct sysv_sem_stats {
    uint64_t start_ns;
    uint64_t end_ns;
    uint64_t count;
    int16_t  sem_op_val;
    uint16_t sem_flg;
    uint32_t padding;
};

void sysv_sem_dump_print_header();
void sysv_sem_dump_emit(const sysv_sem_key &key, uint64_t window_start,
                        uint64_t window_end, uint64_t count,
                        int16_t sem_op_val, uint16_t sem_flg);

#endif
