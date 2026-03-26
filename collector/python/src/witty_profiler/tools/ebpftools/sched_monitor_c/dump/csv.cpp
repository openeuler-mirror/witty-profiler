#include "dump/sched_dump.h"

#include <iostream>

void sched_dump_print_header()
{
    std::cout << "pid,tgid,cpu,time" << std::endl;
}

void sched_dump_emit(const std::vector<sched_entry> &entries)
{
    for (const auto &entry : entries)
    {
        std::cout << entry.key.pid << ","
                  << entry.key.tgid << ","
                  << entry.key.cpu << ","
                  << entry.time_ns << std::endl;
    }
    std::cout.flush();
}

const char *sched_dump_style()
{
    return "csv";
}

int sched_dump_style_id()
{
    return SCHED_OUTPUT_CSV;
}
