#include "dump/cache_miss_dump.h"

#include <iostream>

void cache_miss_dump_print_header()
{
    std::cout << "cpu,tgid,pid,total,l1i,llc" << std::endl;
}

void cache_miss_dump_emit(const std::vector<cache_miss_entry> &entries)
{
    for (const auto &entry : entries)
    {
        const __u64 total = entry.l1i + entry.llc;
        std::cout << entry.key.cpu << ","
                  << entry.key.tgid << ","
                  << entry.key.pid << ","
                  << total << ","
                  << entry.l1i << ","
                  << entry.llc << std::endl;
    }
    std::cout.flush();
}

const char *cache_miss_dump_style()
{
    return "csv";
}

int cache_miss_dump_style_id()
{
    return CACHE_MISS_OUTPUT_CSV;
}
