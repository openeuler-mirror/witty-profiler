#include "sysv_sem_dump.h"
#include <iostream>

void sysv_sem_dump_print_header()
{
    std::cout << "timestamp,pid,tid,semid,sem_num,sem_op_type,count,sem_op_val,sem_flg" << std::endl;
}

void sysv_sem_dump_emit(const sysv_sem_key &key, uint64_t window_start,
                        uint64_t window_end, uint64_t count,
                        int16_t sem_op_val, uint16_t sem_flg)
{
    const char *op_type_str = "wait";
    if (key.sem_op_type == 1)
        op_type_str = "signal";
    else if (key.sem_op_type == 2)
        op_type_str = "wait";

    std::cout << window_end << ","
              << key.pid << ","
              << key.tid << ","
              << key.semid << ","
              << key.sem_num << ","
              << op_type_str << ","
              << count << ","
              << sem_op_val << ","
              << sem_flg << std::endl;
}
