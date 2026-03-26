#include "dump/pmu_dump.h"

#include <iostream>
#include <iomanip>

void pmu_dump_print_header()
{
    std::cout << "sccl_id,event_type,event_code,count,interval_sec" << std::endl;
}

void pmu_dump_emit(const std::vector<pmu_entry> &entries, double interval_sec)
{
    for (const auto &e : entries)
    {
        std::cout << e.key.sccl_id << ","
                  << e.key.event_type << ","
                  << e.key.event_code << ","
                  << e.count << ","
                  << std::fixed << std::setprecision(6) << interval_sec
                  << std::endl;
    }
    std::cout.flush();
}

const char *pmu_dump_style()
{
    return "csv";
}

int pmu_dump_style_id()
{
    return PMU_OUTPUT_CSV;
}
