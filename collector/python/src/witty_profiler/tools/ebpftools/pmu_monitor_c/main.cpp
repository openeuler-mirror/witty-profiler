/* Userspace loader for Huawei Kunpeng uncore PMU eBPF monitor.
 *
 * Discovers PMU devices via /sys/devices/hisi_sccl*_*  and
 * /sys/devices/hisi_siclpmu*_pa0, attaches one BPF handler stub per
 * (device, event) pair through perf_event_open(), and rotates the
 * double-buffer maps on a configurable interval.
 *
 * Usage:
 *   pmu_monitor -i 1.0                    # Monitor all SCCLs
 *   pmu_monitor -i 1.0 -t 1               # Monitor only SCCL 1
 *   pmu_monitor -i 1.0 -t 1,3,5           # Monitor SCCL 1, 3, 5
 */

#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <linux/perf_event.h>
#include <signal.h>
#include <sys/ioctl.h>
#include <sys/resource.h>
#include <sys/syscall.h>
#include <unistd.h>

#include <cerrno>
#include <climits>
#include <cstdarg>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>
#include <algorithm>
#include <set>
#include <map>
#include <dirent.h>
#include <glob.h>
#include <fstream>
#include <sstream>

#include "pmu_version.h"
#include "dump/pmu_dump.h"

/* Mirrors the kernel-side pmu_config; must stay in sync with pmu_common.h */
struct pmu_config {
    __u32 target_sccl;
    __u8  active_map;
    __u8  enable_ddr;
    __u8  enable_hha;
    __u8  enable_l3c;
    __u8  enable_pa;
    __u8  reserved[3];
};

/* Mirrors kernel-side event_slot */
struct event_slot {
    __u32 sccl_id;
    __u32 event_type;
    __u32 event_code;
    __u32 valid;
};

struct pmu_device {
    __u32 sccl_id;
    __u32 event_type;
    __u32 perf_type;
    std::string sysfs_name;
    int cpu;  /* CPU to use for perf_event_open */
};

static volatile bool exiting = false;

static int libbpf_print_fn(enum libbpf_print_level level, const char *fmt, va_list args)
{
    if (level == LIBBPF_DEBUG)
        return 0;
    return vfprintf(stderr, fmt, args);
}

static void handle_sigint(int)
{
    exiting = true;
}

static bool bump_memlock()
{
    struct rlimit rlim = {RLIM_INFINITY, RLIM_INFINITY};
    return setrlimit(RLIMIT_MEMLOCK, &rlim) == 0;
}

static std::string default_obj_path()
{
    char exe_path[PATH_MAX] = {0};
    ssize_t len = readlink("/proc/self/exe", exe_path, sizeof(exe_path) - 1);
    if (len > 0)
    {
        exe_path[len] = '\0';
        std::string exe(exe_path);
        std::string::size_type pos = exe.find_last_of('/');
        if (pos != std::string::npos)
            return exe.substr(0, pos + 1) + "pmu_monitor_bpf.o";
    }
    return "pmu_monitor_bpf.o";
}

static int perf_event_open(struct perf_event_attr *attr, pid_t pid, int cpu,
                           int group_fd, unsigned long flags)
{
    return static_cast<int>(syscall(__NR_perf_event_open, attr, pid, cpu, group_fd, flags));
}

static void usage(const char *prog)
{
    std::cerr << "Usage: " << prog
              << " [-v] [-i interval_sec] [-d duration_sec] [-s sample_period]"
              << " [-t target_sccl] [-o bpf_obj_path]" << std::endl
              << "  -v              Print version and exit" << std::endl
              << "  -i interval_sec Output interval in seconds (default: 1)" << std::endl
              << "  -d duration_sec Total run duration, 0 for infinite (default: 0)" << std::endl
              << "  -s sample_period PMU sample period (default: 1000)" << std::endl
              << "  -t target_sccl  Target SCCL(s), comma-separated (default: all)" << std::endl
              << "                  Example: -t 1 or -t 1,3,5,7" << std::endl
              << "  -o bpf_obj_path Path to BPF object file" << std::endl;
}

static void clear_count_map(int map_fd)
{
    pmu_key cur_key = {};
    int res = bpf_map_get_next_key(map_fd, nullptr, &cur_key);
    while (res == 0)
    {
        pmu_key next_key = {};
        res = bpf_map_get_next_key(map_fd, &cur_key, &next_key);
        bpf_map_delete_elem(map_fd, &cur_key);
        if (res == 0)
            cur_key = next_key;
    }
}

static void reset_drop_count(int map_fd)
{
    __u32 key = 0;
    __u64 zero = 0;
    bpf_map_update_elem(map_fd, &key, &zero, BPF_ANY);
}

static __u64 read_drop_count(int map_fd)
{
    __u32 key = 0;
    __u64 value = 0;
    bpf_map_lookup_elem(map_fd, &key, &value);
    return value;
}

static std::vector<pmu_entry> collect_counts(int map_fd)
{
    std::vector<pmu_entry> entries;
    pmu_key cur_key = {};
    int res = bpf_map_get_next_key(map_fd, nullptr, &cur_key);
    while (res == 0)
    {
        pmu_value val = {};
        if (bpf_map_lookup_elem(map_fd, &cur_key, &val) == 0)
            entries.push_back({cur_key, val.count, val.first_ts, val.last_ts});

        pmu_key next_key = {};
        res = bpf_map_get_next_key(map_fd, &cur_key, &next_key);
        if (res == 0)
            cur_key = next_key;
    }

    std::sort(entries.begin(), entries.end(), [](const pmu_entry &lhs, const pmu_entry &rhs) {
        if (lhs.key.sccl_id != rhs.key.sccl_id)
            return lhs.key.sccl_id < rhs.key.sccl_id;
        if (lhs.key.event_type != rhs.key.event_type)
            return lhs.key.event_type < rhs.key.event_type;
        return lhs.key.event_code < rhs.key.event_code;
    });

    return entries;
}

static const char *output_style_name(unsigned style)
{
    return style == PMU_OUTPUT_MSGSPEC ? "msgspec" : "csv";
}

static bool read_sysfs_int(const std::string &path, __u32 &out)
{
    std::ifstream ifs(path);
    if (!ifs.is_open())
        return false;
    unsigned long val = 0;
    ifs >> val;
    out = static_cast<__u32>(val);
    return !ifs.fail();
}

/* Read cpumask from sysfs and return first valid CPU.
 * Returns -1 if no valid CPU found. */
static int read_sysfs_cpumask(const std::string &dev_path)
{
    std::string cpumask_path = dev_path + "/cpumask";
    std::ifstream ifs(cpumask_path);
    if (!ifs.is_open())
        return -1;

    std::string line;
    if (!std::getline(ifs, line))
        return -1;

    /* Parse cpumask: could be hex (0xff) or comma-separated list (0-3) */
    /* Try comma-separated range first (e.g., "0-3") */
    size_t dash_pos = line.find('-');
    if (dash_pos != std::string::npos)
    {
        try
        {
            int start = std::stoi(line.substr(0, dash_pos));
            return start;  /* Use first CPU in range */
        }
        catch (...)
        {
        }
    }

    /* Try parsing as hex mask */
    if (line.substr(0, 2) == "0x" || line.substr(0, 2) == "0X")
    {
        try
        {
            unsigned long mask = std::stoul(line, nullptr, 16);
            for (int cpu = 0; cpu < 64 && mask; ++cpu)
            {
                if (mask & 1)
                    return cpu;
                mask >>= 1;
            }
        }
        catch (...)
        {
        }
    }

    /* Try parsing as single number */
    try
    {
        return std::stoi(line);
    }
    catch (...)
    {
    }

    return -1;
}

/* Parse SCCL ID from device name.
 * Examples: hisi_sccl3_ddrc0 -> 3, hisi_sccl15_hha2 -> 15 */
static bool parse_sccl_id(const std::string &dev_name, __u32 &sccl_id)
{
    auto pos = dev_name.find("sccl");
    if (pos == std::string::npos)
        return false;
    pos += 4; /* skip "sccl" */
    std::string num_str;
    while (pos < dev_name.size() && dev_name[pos] >= '0' && dev_name[pos] <= '9')
    {
        num_str.push_back(dev_name[pos]);
        ++pos;
    }
    if (num_str.empty())
        return false;
    sccl_id = static_cast<__u32>(std::stoul(num_str));
    return true;
}

/* Parse SICL ID from PA device name.
 * Example: hisi_siclpmu1_pa0 -> sccl_id derived from sicl_id */
static bool parse_sicl_pa(const std::string &dev_name, __u32 &sccl_id)
{
    auto pos = dev_name.find("siclpmu");
    if (pos == std::string::npos)
        return false;
    pos += 7; /* skip "siclpmu" */
    std::string num_str;
    while (pos < dev_name.size() && dev_name[pos] >= '0' && dev_name[pos] <= '9')
    {
        num_str.push_back(dev_name[pos]);
        ++pos;
    }
    if (num_str.empty())
        return false;
    /* Use SICL ID directly as the sccl_id key for PA events */
    sccl_id = static_cast<__u32>(std::stoul(num_str));
    return true;
}

enum {
    EVENT_DDR = 0,
    EVENT_HHA = 1,
    EVENT_L3C = 2,
    EVENT_PA  = 3,
};

static std::vector<pmu_device> discover_pmu_devices()
{
    struct glob_spec {
        const char *pattern;
        __u32 event_type;
        bool is_pa;
    };

    static const glob_spec specs[] = {
        {"/sys/devices/hisi_sccl*_ddrc*/type", EVENT_DDR, false},
        {"/sys/devices/hisi_sccl*_hha*/type",  EVENT_HHA, false},
        {"/sys/devices/hisi_sccl*_l3c*/type",  EVENT_L3C, false},
        {"/sys/devices/hisi_siclpmu*_pa0/type", EVENT_PA,  true},
    };

    std::vector<pmu_device> devices;

    for (const auto &spec : specs)
    {
        glob_t globbuf = {};
        if (glob(spec.pattern, 0, nullptr, &globbuf) != 0)
        {
            globfree(&globbuf);
            continue;
        }

        for (size_t i = 0; i < globbuf.gl_pathc; ++i)
        {
            std::string type_path(globbuf.gl_pathv[i]);
            __u32 perf_type = 0;
            if (!read_sysfs_int(type_path, perf_type))
                continue;

            std::string dir = type_path.substr(0, type_path.rfind('/'));
            std::string dev_name = dir.substr(dir.rfind('/') + 1);

            __u32 sccl_id = 0;
            bool ok = spec.is_pa ? parse_sicl_pa(dev_name, sccl_id)
                                 : parse_sccl_id(dev_name, sccl_id);
            if (!ok)
                continue;

            /* Read cpumask to find valid CPU for this device */
            int cpu = read_sysfs_cpumask(dir);
            if (cpu < 0)
            {
                std::clog << "[warn] No valid cpumask for " << dev_name << ", skipping" << std::endl;
                continue;
            }

            devices.push_back({sccl_id, spec.event_type, perf_type, dev_name, cpu});
        }
        globfree(&globbuf);
    }

    std::sort(devices.begin(), devices.end(), [](const pmu_device &a, const pmu_device &b) {
        if (a.event_type != b.event_type)
            return a.event_type < b.event_type;
        return a.sccl_id < b.sccl_id;
    });

    return devices;
}

struct event_code_set {
    __u32 event_type;
    std::vector<__u32> codes;
};

/* Event name to code mapping for dynamic discovery */
struct event_name_spec {
    __u32 event_type;
    std::string name;
};

/* Required events for each event type */
static const std::vector<event_name_spec> required_events = {
    /* DDR events */
    {EVENT_DDR, "flux_wr"},
    {EVENT_DDR, "flux_rd"},
    /* HHA events */
    {EVENT_HHA, "rx_operations"},
    {EVENT_HHA, "rx_outer"},
    {EVENT_HHA, "rx_sccl"},
    {EVENT_HHA, "rd_ddr_64b"},
    {EVENT_HHA, "wr_ddr_64b"},
    {EVENT_HHA, "rd_ddr_128b"},
    {EVENT_HHA, "wr_ddr_128b"},
    /* L3C events */
    {EVENT_L3C, "rd_cpipe"},
    {EVENT_L3C, "wr_cpipe"},
    {EVENT_L3C, "rd_hit_cpipe"},
    {EVENT_L3C, "wr_hit_cpipe"},
    {EVENT_L3C, "rd_spipe"},
    {EVENT_L3C, "wr_spipe"},
    {EVENT_L3C, "rd_hit_spipe"},
    {EVENT_L3C, "wr_hit_spipe"},
    {EVENT_L3C, "back_invalid"},
    {EVENT_L3C, "retry_cpu"},
    /* PA events */
    {EVENT_PA, "rx_flit0"},
    {EVENT_PA, "rx_flit1"},
    {EVENT_PA, "rx_flit2"},
    {EVENT_PA, "rx_flit3"},
    {EVENT_PA, "tx_flit0"},
    {EVENT_PA, "tx_flit1"},
    {EVENT_PA, "tx_flit2"},
    {EVENT_PA, "tx_flit3"},
    {EVENT_PA, "cycles"},
};

/* Parse event config from sysfs format: "config=0xNN" or "config=NN" */
static bool parse_event_config(const std::string &content, __u32 &config)
{
    size_t pos = content.find("config=");
    if (pos == std::string::npos)
        return false;
    
    pos += 7;  /* skip "config=" */
    std::string val_str;
    while (pos < content.size() && !isspace(content[pos]))
    {
        val_str.push_back(content[pos]);
        ++pos;
    }
    
    try
    {
        if (val_str.substr(0, 2) == "0x" || val_str.substr(0, 2) == "0X")
            config = static_cast<__u32>(std::stoul(val_str, nullptr, 16));
        else
            config = static_cast<__u32>(std::stoul(val_str));
        return true;
    }
    catch (...)
    {
        return false;
    }
}

/* Discover event codes from sysfs for a specific device */
static std::map<std::string, __u32> discover_device_events(const std::string &dev_path)
{
    std::map<std::string, __u32> events;
    std::string events_dir = dev_path + "/events";
    
    DIR *dir = opendir(events_dir.c_str());
    if (!dir)
        return events;
    
    struct dirent *entry;
    while ((entry = readdir(dir)) != nullptr)
    {
        if (entry->d_name[0] == '.')
            continue;
        
        std::string event_name(entry->d_name);
        std::string event_path = events_dir + "/" + event_name;
        
        std::ifstream ifs(event_path);
        if (!ifs.is_open())
            continue;
        
        std::string content;
        if (std::getline(ifs, content))
        {
            __u32 config = 0;
            if (parse_event_config(content, config))
                events[event_name] = config;
        }
    }
    
    closedir(dir);
    return events;
}

/* Build event codes from discovered events */
static std::vector<event_code_set> build_event_codes(
    const std::map<std::string, __u32> &ddr_events,
    const std::map<std::string, __u32> &hha_events,
    const std::map<std::string, __u32> &l3c_events,
    const std::map<std::string, __u32> &pa_events)
{
    std::vector<event_code_set> result(4);  /* DDR, HHA, L3C, PA */
    
    /* DDR events */
    auto it = ddr_events.find("flux_wr");
    if (it != ddr_events.end())
        result[EVENT_DDR].codes.push_back(it->second);
    it = ddr_events.find("flux_rd");
    if (it != ddr_events.end())
        result[EVENT_DDR].codes.push_back(it->second);
    result[EVENT_DDR].event_type = EVENT_DDR;
    
    /* HHA events */
    const char *hha_names[] = {"rx_operations", "rx_outer", "rx_sccl",
                               "rd_ddr_64b", "wr_ddr_64b", "rd_ddr_128b", "wr_ddr_128b"};
    for (const char *name : hha_names)
    {
        it = hha_events.find(name);
        if (it != hha_events.end())
            result[EVENT_HHA].codes.push_back(it->second);
    }
    result[EVENT_HHA].event_type = EVENT_HHA;
    
    /* L3C events */
    const char *l3c_names[] = {"rd_cpipe", "wr_cpipe", "rd_hit_cpipe", "wr_hit_cpipe",
                               "rd_spipe", "wr_spipe", "rd_hit_spipe", "wr_hit_spipe",
                               "back_invalid", "retry_cpu"};
    for (const char *name : l3c_names)
    {
        it = l3c_events.find(name);
        if (it != l3c_events.end())
            result[EVENT_L3C].codes.push_back(it->second);
    }
    result[EVENT_L3C].event_type = EVENT_L3C;
    
    /* PA events */
    const char *pa_names[] = {"rx_flit0", "rx_flit1", "rx_flit2", "rx_flit3",
                              "tx_flit0", "tx_flit1", "tx_flit2", "tx_flit3", "cycles"};
    for (const char *name : pa_names)
    {
        it = pa_events.find(name);
        if (it != pa_events.end())
            result[EVENT_PA].codes.push_back(it->second);
    }
    result[EVENT_PA].event_type = EVENT_PA;
    
    return result;
}

/* Fallback event codes if discovery fails */
static std::vector<event_code_set> fallback_event_codes()
{
    return {
        /* DDR: flux_wr (0x0), flux_rd (0x1) - common default */
        {EVENT_DDR, {0x0, 0x1}},
        /* HHA: standard codes */
        {EVENT_HHA, {0x00, 0x01, 0x02, 0x1C, 0x1D, 0x1E, 0x1F}},
        /* L3C: standard codes */
        {EVENT_L3C, {0x00, 0x01, 0x02, 0x03, 0x20, 0x21, 0x22, 0x23, 0x29, 0xB8}},
        /* PA: standard codes */
        {EVENT_PA, {0x40, 0x44, 0x48, 0x4C, 0x50, 0x54, 0x58, 0x5C, 0x78}},
    };
}

/* Parse comma-separated SCCL IDs: "1,3,5" -> {1, 3, 5} */
static std::set<__u32> parse_sccl_targets(const std::string &s)
{
    std::set<__u32> result;
    std::stringstream ss(s);
    std::string token;
    while (std::getline(ss, token, ','))
    {
        try
        {
            __u32 id = static_cast<__u32>(std::stoul(token));
            result.insert(id);
        }
        catch (...)
        {
            std::cerr << "Invalid SCCL ID: " << token << std::endl;
        }
    }
    return result;
}

/* Must match MAX_EVENT_SLOTS in pmu_monitor.bpf.c */
static constexpr int MAX_BPF_SLOTS = 256;

int main(int argc, char **argv)
{
    std::string obj_path = default_obj_path();
    int interval_sec = 1;
    int duration_sec = 0;
    long long sample_period = 1000;
    bool print_version = false;
    std::string target_sccl_str;
    std::set<__u32> target_sccls;

    int opt;
    while ((opt = getopt(argc, argv, "vi:d:s:t:o:h")) != -1)
    {
        switch (opt)
        {
        case 'v':
            print_version = true;
            break;
        case 'i':
            interval_sec = std::atoi(optarg);
            break;
        case 'd':
            duration_sec = std::atoi(optarg);
            break;
        case 's':
            sample_period = std::atoll(optarg);
            break;
        case 't':
            target_sccl_str = optarg;
            target_sccls = parse_sccl_targets(target_sccl_str);
            break;
        case 'o':
            obj_path = optarg;
            break;
        case 'h':
        default:
            usage(argv[0]);
            return 1;
        }
    }

    if (print_version)
    {
        std::cout << "output_style:" << pmu_dump_style()
                  << " (" << pmu_dump_style_id() << ")" << std::endl;
        return 0;
    }

    if (!bump_memlock())
    {
        std::cerr << "Failed to raise memlock limit: " << strerror(errno) << std::endl;
        return 1;
    }

    libbpf_set_strict_mode(LIBBPF_STRICT_ALL);
    libbpf_set_print(libbpf_print_fn);

    bpf_object *obj = bpf_object__open_file(obj_path.c_str(), nullptr);
    if (!obj)
    {
        std::cerr << "Failed to open BPF object: " << obj_path << " errno=" << errno << std::endl;
        return 1;
    }

    if (bpf_object__load(obj))
    {
        std::cerr << "Failed to load BPF object: errno=" << -errno << std::endl;
        bpf_object__close(obj);
        return 1;
    }

    bpf_map *cfg_map  = bpf_object__find_map_by_name(obj, "config_map");
    bpf_map *map0     = bpf_object__find_map_by_name(obj, "pmu_map0");
    bpf_map *map1     = bpf_object__find_map_by_name(obj, "pmu_map1");
    bpf_map *drop_map = bpf_object__find_map_by_name(obj, "drop_count_map");
    bpf_map *slot_map = bpf_object__find_map_by_name(obj, "event_slot_map");
    if (!cfg_map || !map0 || !map1 || !drop_map || !slot_map)
    {
        std::cerr << "Required maps not found in BPF object" << std::endl;
        bpf_object__close(obj);
        return 1;
    }

    bpf_map *rodata_map = bpf_object__find_map_by_name(obj, ".rodata");
    if (rodata_map)
    {
        size_t rodata_size = 0;
        const void *init_data = bpf_map__initial_value(rodata_map, &rodata_size);
        if (init_data && rodata_size >= sizeof(struct pmu_version))
        {
            struct pmu_version ebpf_ver = {};
            std::memcpy(&ebpf_ver, init_data, sizeof(ebpf_ver));
            if (ebpf_ver.output_style != static_cast<unsigned>(pmu_dump_style_id()))
            {
                std::cerr << "eBPF output style mismatch. ebpf="
                          << output_style_name(ebpf_ver.output_style)
                          << " host=" << pmu_dump_style() << std::endl;
                bpf_object__close(obj);
                return 1;
            }
        }
    }

    /* handle_pmu_slot_0 .. handle_pmu_slot_255 (must match BPF stub count) */
    bpf_program *slot_progs[MAX_BPF_SLOTS] = {};
    for (int i = 0; i < MAX_BPF_SLOTS; ++i)
    {
        char name[64];
        snprintf(name, sizeof(name), "handle_pmu_slot_%d", i);
        slot_progs[i] = bpf_object__find_program_by_name(obj, name);
    }

    std::vector<pmu_device> all_devices = discover_pmu_devices();
    if (all_devices.empty())
    {
        std::cerr << "No Huawei uncore PMU devices found in /sys/devices/" << std::endl;
        bpf_object__close(obj);
        return 1;
    }
    std::clog << "[init] Discovered " << all_devices.size() << " PMU device(s)" << std::endl;

    /* Filter devices by target SCCLs if specified */
    std::vector<pmu_device> devices;
    if (!target_sccls.empty())
    {
        for (const auto &dev : all_devices)
        {
            if (target_sccls.count(dev.sccl_id))
                devices.push_back(dev);
        }
        std::clog << "[init] Filtered to " << devices.size()
                  << " device(s) for SCCL(s): ";
        for (auto it = target_sccls.begin(); it != target_sccls.end(); ++it)
        {
            if (it != target_sccls.begin())
                std::clog << ",";
            std::clog << *it;
        }
        std::clog << std::endl;
    }
    else
    {
        devices = all_devices;
    }

    if (devices.empty())
    {
        std::cerr << "No PMU devices match the target SCCL filter" << std::endl;
        bpf_object__close(obj);
        return 1;
    }

    /* Discover event codes from sysfs for compatibility */
    std::map<std::string, __u32> ddr_events, hha_events, l3c_events, pa_events;
    
    /* Find one device of each type to discover events */
    for (const auto &dev : devices)
    {
        std::string dev_path = "/sys/devices/" + dev.sysfs_name;
        if (dev.event_type == EVENT_DDR && ddr_events.empty())
        {
            ddr_events = discover_device_events(dev_path);
            if (!ddr_events.empty())
                std::clog << "[init] Discovered " << ddr_events.size() 
                          << " DDR events from " << dev.sysfs_name << std::endl;
        }
        else if (dev.event_type == EVENT_HHA && hha_events.empty())
        {
            hha_events = discover_device_events(dev_path);
            if (!hha_events.empty())
                std::clog << "[init] Discovered " << hha_events.size() 
                          << " HHA events from " << dev.sysfs_name << std::endl;
        }
        else if (dev.event_type == EVENT_L3C && l3c_events.empty())
        {
            l3c_events = discover_device_events(dev_path);
            if (!l3c_events.empty())
                std::clog << "[init] Discovered " << l3c_events.size() 
                          << " L3C events from " << dev.sysfs_name << std::endl;
        }
        else if (dev.event_type == EVENT_PA && pa_events.empty())
        {
            pa_events = discover_device_events(dev_path);
            if (!pa_events.empty())
                std::clog << "[init] Discovered " << pa_events.size() 
                          << " PA events from " << dev.sysfs_name << std::endl;
        }
    }
    
    /* Build event codes from discovered events, or use fallback */
    std::vector<event_code_set> event_codes;
    if (!ddr_events.empty() || !hha_events.empty() || !l3c_events.empty() || !pa_events.empty())
    {
        event_codes = build_event_codes(ddr_events, hha_events, l3c_events, pa_events);
        std::clog << "[init] Using dynamically discovered event codes" << std::endl;
    }
    else
    {
        event_codes = fallback_event_codes();
        std::clog << "[init] Using fallback event codes (no events discovered)" << std::endl;
    }
    
    /* Log discovered event codes */
    for (const auto &ec : event_codes)
    {
        if (ec.codes.empty())
            continue;
        const char *type_name = ec.event_type == EVENT_DDR ? "DDR" :
                                ec.event_type == EVENT_HHA ? "HHA" :
                                ec.event_type == EVENT_L3C ? "L3C" : "PA";
        std::clog << "[init] " << type_name << " events: ";
        for (size_t i = 0; i < ec.codes.size(); ++i)
        {
            if (i > 0)
                std::clog << ",";
            std::clog << "0x" << std::hex << ec.codes[i] << std::dec;
        }
        std::clog << std::endl;
    }

    /* event_type -> codes lookup; indices match hccs_event_type enum */
    std::vector<__u32> codes_for_type[4];
    for (const auto &ec : event_codes)
    {
        if (ec.event_type < 4)
            codes_for_type[ec.event_type] = ec.codes;
    }

    std::vector<int> perf_fds;
    std::vector<bpf_link *> links;
    int slot_idx = 0;
    int failed_count = 0;

    for (const auto &dev : devices)
    {
        if (dev.event_type >= 4)
            continue;

        const auto &codes = codes_for_type[dev.event_type];
        for (__u32 code : codes)
        {
            if (slot_idx >= MAX_BPF_SLOTS)
            {
                std::clog << "[warn] Exceeded " << MAX_BPF_SLOTS
                          << " slot handlers; remaining events skipped" << std::endl;
                goto attach_done;
            }

            if (!slot_progs[slot_idx])
            {
                std::clog << "[warn] BPF handler handle_pmu_slot_" << slot_idx
                          << " not found; skipping" << std::endl;
                ++slot_idx;
                continue;
            }

            /* Populate event_slot_map: BPF handler reads this to identify the event */
            event_slot slot = {dev.sccl_id, dev.event_type, code, 1};
            __u32 slot_key = static_cast<__u32>(slot_idx);
            if (bpf_map_update_elem(bpf_map__fd(slot_map), &slot_key, &slot, BPF_ANY) != 0)
            {
                std::cerr << "Failed to update event_slot_map[" << slot_idx
                          << "]: " << strerror(errno) << std::endl;
                ++slot_idx;
                continue;
            }

            /* perf_event_open for this uncore PMU device.
             * attr.type comes from the device sysfs, attr.config is the event code.
             * pid=-1, cpu from device cpumask for uncore PMU. */
            struct perf_event_attr attr = {};
            attr.type = dev.perf_type;
            attr.size = sizeof(struct perf_event_attr);
            attr.config = code;
            attr.sample_period = sample_period;
            attr.disabled = 1;
            attr.exclude_kernel = 0;
            attr.exclude_hv = 1;

            int perf_fd = perf_event_open(&attr, -1, dev.cpu, -1, 0);
            if (perf_fd < 0)
            {
                std::clog << "[warn] perf_event_open failed for " << dev.sysfs_name
                          << " code=0x" << std::hex << code << std::dec
                          << ": " << strerror(errno) << std::endl;
                ++failed_count;
                ++slot_idx;
                continue;
            }

            bpf_link *link = bpf_program__attach_perf_event(slot_progs[slot_idx], perf_fd);
            long err = libbpf_get_error(link);
            if (err)
            {
                std::cerr << "Failed to attach slot " << slot_idx
                          << " to " << dev.sysfs_name
                          << ": " << strerror(static_cast<int>(-err)) << std::endl;
                close(perf_fd);
                ++slot_idx;
                continue;
            }

            perf_fds.push_back(perf_fd);
            links.push_back(link);
            ++slot_idx;
        }
    }

attach_done:
    if (perf_fds.empty())
    {
        std::cerr << "Failed to attach any perf events (" << failed_count << " failures)" << std::endl;
        bpf_object__close(obj);
        return 1;
    }
    std::clog << "[init] Attached " << perf_fds.size() << " perf event(s) in "
              << slot_idx << " slot(s), " << failed_count << " failure(s)" << std::endl;

    __u32 cfg_key = 0;
    pmu_config cfg = {};
    cfg.target_sccl = target_sccls.empty() ? 0xFFFFFFFF : (*target_sccls.begin());
    cfg.active_map  = 0;
    cfg.enable_ddr  = 1;
    cfg.enable_hha  = 1;
    cfg.enable_l3c  = 1;
    cfg.enable_pa   = 1;

    if (bpf_map_update_elem(bpf_map__fd(cfg_map), &cfg_key, &cfg, BPF_ANY) != 0)
    {
        std::cerr << "Failed to update config_map: errno=" << errno << std::endl;
        for (bpf_link *link : links)
            bpf_link__destroy(link);
        for (int fd : perf_fds)
            close(fd);
        bpf_object__close(obj);
        return 1;
    }

    clear_count_map(bpf_map__fd(map0));
    clear_count_map(bpf_map__fd(map1));
    reset_drop_count(bpf_map__fd(drop_map));

    signal(SIGINT, handle_sigint);
    signal(SIGTERM, handle_sigint);

    /* Enable all perf events */
    for (int fd : perf_fds)
    {
        if (ioctl(fd, PERF_EVENT_IOC_RESET, 0) < 0)
            std::cerr << "Failed to reset perf event: " << strerror(errno) << std::endl;
        if (ioctl(fd, PERF_EVENT_IOC_ENABLE, 0) < 0)
        {
            std::cerr << "Failed to enable perf event: " << strerror(errno) << std::endl;
            for (bpf_link *link : links)
                bpf_link__destroy(link);
            for (int f : perf_fds)
                close(f);
            bpf_object__close(obj);
            return 1;
        }
    }

    pmu_dump_print_header();

    int remaining = duration_sec;
    while (!exiting && (remaining > 0 || duration_sec == 0))
    {
        int sleep_sec = interval_sec > 0 ? interval_sec : 1;
        sleep(sleep_sec);
        if (duration_sec > 0)
            remaining -= sleep_sec;

        /* Rotate double-buffer: swap active_map, read the now-inactive one */
        int read_map_idx = cfg.active_map;
        cfg.active_map = static_cast<__u8>(1 - cfg.active_map);
        if (bpf_map_update_elem(bpf_map__fd(cfg_map), &cfg_key, &cfg, BPF_ANY) != 0)
        {
            std::cerr << "Failed to switch active map: errno=" << errno << std::endl;
            break;
        }

        int map_fd = read_map_idx == 0 ? bpf_map__fd(map0) : bpf_map__fd(map1);
        std::vector<pmu_entry> entries = collect_counts(map_fd);
        clear_count_map(map_fd);

        __u64 drops = read_drop_count(bpf_map__fd(drop_map));
        reset_drop_count(bpf_map__fd(drop_map));
        std::clog << "[window] entries=" << entries.size() << " drops=" << drops << std::endl;

        pmu_dump_emit(entries, static_cast<double>(sleep_sec));

        if (entries.empty() && drops == 0)
        {
            for (int fd : perf_fds)
            {
                ioctl(fd, PERF_EVENT_IOC_RESET, 0);
                ioctl(fd, PERF_EVENT_IOC_ENABLE, 0);
            }
        }
    }

    for (int fd : perf_fds)
        ioctl(fd, PERF_EVENT_IOC_DISABLE, 0);

    for (bpf_link *link : links)
        bpf_link__destroy(link);
    for (int fd : perf_fds)
        close(fd);
    bpf_object__close(obj);
    return 0;
}
