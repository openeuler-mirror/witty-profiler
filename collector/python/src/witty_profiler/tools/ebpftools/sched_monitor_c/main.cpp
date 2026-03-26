// User-space loader for sched monitor.

#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <signal.h>
#include <sys/resource.h>
#include <unistd.h>

#include <cerrno>
#include <climits>
#include <cstdarg>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>

#include "dump/sched_dump.h"
#include "sched_version.h"

struct sched_config {
    __u32 tgid_filter_enabled;
    __u32 pid_filter_enabled;
    __u32 cpu_filter_enabled;
    __u8 active_map;
    __u8 reserved1;
    __u16 reserved2;
};

// Whether the running kernel supports batch map operations (>= 5.6).
// Lazily detected on first use; once set to false, all subsequent calls
// fall back to the iterative path.
static bool batch_ops_supported = true;

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
            return exe.substr(0, pos + 1) + "sched_monitor_bpf.o";
    }
    return "sched_monitor_bpf.o";
}

static void usage(const char *prog)
{
    std::cerr << "Usage: " << prog
              << " [-v] [-t pid... ] [-p tgid... ] [-cpu cpu... ]"
              << " [-d duration_sec] [-i interval_sec] [-m max_entry] [-o bpf_obj_path]" << std::endl;
}

// ---- iterative fallback (kernel < 5.6) ------------------------------------

static void clear_stats_map_iter(int map_fd)
{
    sched_key cur_key = {};
    int res = bpf_map_get_next_key(map_fd, nullptr, &cur_key);
    while (res == 0)
    {
        sched_key next_key = {};
        res = bpf_map_get_next_key(map_fd, &cur_key, &next_key);
        bpf_map_delete_elem(map_fd, &cur_key);
        if (res == 0)
            cur_key = next_key;
    }
}

static std::vector<sched_entry> collect_stats_iter(int map_fd, __u32 reserve_hint)
{
    std::vector<sched_entry> entries;
    entries.reserve(reserve_hint);

    sched_key cur_key = {};
    int res = bpf_map_get_next_key(map_fd, nullptr, &cur_key);
    while (res == 0)
    {
        __u64 time_ns = 0;
        if (bpf_map_lookup_elem(map_fd, &cur_key, &time_ns) == 0)
            entries.push_back({cur_key, time_ns});

        sched_key next_key = {};
        res = bpf_map_get_next_key(map_fd, &cur_key, &next_key);
        if (res == 0)
            cur_key = next_key;
    }

    return entries;
}

// ---- batch path (kernel >= 5.6) -------------------------------------------

static constexpr __u32 BATCH_SIZE = 4096;

// Batch collect-and-delete: uses bpf_map_lookup_and_delete_batch so a single
// syscall both reads and removes entries, halving the number of round-trips
// compared to separate lookup_batch + delete_batch.
static std::vector<sched_entry> collect_and_clear_batch(int map_fd, __u32 reserve_hint)
{
    std::vector<sched_entry> entries;
    entries.reserve(reserve_hint);

    std::vector<sched_key> keys(BATCH_SIZE);
    std::vector<__u64> values(BATCH_SIZE);

    LIBBPF_OPTS(bpf_map_batch_opts, opts);

    void *in_batch = nullptr;
    void *out_batch = nullptr;

    for (;;)
    {
        __u32 count = BATCH_SIZE;
        int err = bpf_map_lookup_and_delete_batch(
            map_fd, &in_batch, &out_batch,
            keys.data(), values.data(), &count, &opts);

        if (err && errno == EINVAL)
        {
            // Kernel does not support batch ops – disable globally and let
            // the caller fall back to the iterative path.
            batch_ops_supported = false;
            return {};
        }

        for (__u32 i = 0; i < count; ++i)
            entries.push_back({keys[i], values[i]});

        if (err && errno == ENOENT)
            break; // all entries consumed
        if (err)
        {
            std::cerr << "bpf_map_lookup_and_delete_batch: " << strerror(errno) << std::endl;
            break;
        }

        in_batch = out_batch;
    }

    return entries;
}

static const char *output_style_name(unsigned style)
{
    return style == SCHED_OUTPUT_MSGSPEC ? "msgspec" : "csv";
}

static bool is_flag(const char *arg)
{
    return arg && arg[0] == '-';
}

static void parse_id_list(int argc, char **argv, int &idx, std::vector<int> &out)
{
    while (idx < argc && !is_flag(argv[idx]))
    {
        out.push_back(std::atoi(argv[idx]));
        ++idx;
    }
}

int main(int argc, char **argv)
{
    std::string obj_path = default_obj_path();
    std::vector<int> pid_list;
    std::vector<int> tgid_list;
    std::vector<int> cpu_list;
    int duration_sec = 0;
    int interval_sec = 2;
    int max_entry = 262144;
    bool print_version = false;

    for (int i = 1; i < argc;)
    {
        if (std::strcmp(argv[i], "-v") == 0)
        {
            print_version = true;
            ++i;
        }
        else if (std::strcmp(argv[i], "-t") == 0)
        {
            i++;
            parse_id_list(argc, argv, i, pid_list);
        }
        else if (std::strcmp(argv[i], "-p") == 0)
        {
            i++;
            parse_id_list(argc, argv, i, tgid_list);
        }
        else if (std::strcmp(argv[i], "-cpu") == 0)
        {
            i++;
            parse_id_list(argc, argv, i, cpu_list);
        }
        else if (std::strcmp(argv[i], "-d") == 0 && i + 1 < argc)
        {
            duration_sec = std::atoi(argv[i + 1]);
            i += 2;
        }
        else if (std::strcmp(argv[i], "-i") == 0 && i + 1 < argc)
        {
            interval_sec = std::atoi(argv[i + 1]);
            i += 2;
        }
        else if (std::strcmp(argv[i], "-m") == 0 && i + 1 < argc)
        {
            max_entry = std::atoi(argv[i + 1]);
            i += 2;
        }
        else if (std::strcmp(argv[i], "-o") == 0 && i + 1 < argc)
        {
            obj_path = argv[i + 1];
            i += 2;
        }
        else if (std::strcmp(argv[i], "-h") == 0)
        {
            usage(argv[0]);
            return 0;
        }
        else
        {
            usage(argv[0]);
            return 1;
        }
    }

    if (print_version)
    {
        std::cout << "output_style:" << sched_dump_style() << " (" << sched_dump_style_id() << ")" << std::endl;
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

    bpf_map *cfg_map = bpf_object__find_map_by_name(obj, "config_map");
    bpf_map *stats_map0 = bpf_object__find_map_by_name(obj, "stats_map0");
    bpf_map *stats_map1 = bpf_object__find_map_by_name(obj, "stats_map1");
    bpf_map *tgid_map = bpf_object__find_map_by_name(obj, "allowed_tgid_map");
    bpf_map *pid_map = bpf_object__find_map_by_name(obj, "allowed_pid_map");
    bpf_map *cpu_map = bpf_object__find_map_by_name(obj, "allowed_cpu_map");
    if (!cfg_map || !stats_map0 || !stats_map1 || !tgid_map || !pid_map || !cpu_map)
    {
        std::cerr << "Required maps not found in BPF object" << std::endl;
        bpf_object__close(obj);
        return 1;
    }

    bpf_map__set_max_entries(stats_map0, max_entry);
    bpf_map__set_max_entries(stats_map1, max_entry);
    bpf_map__set_max_entries(tgid_map, max_entry);
    bpf_map__set_max_entries(pid_map, max_entry);
    bpf_map__set_max_entries(cpu_map, max_entry);

    if (bpf_object__load(obj))
    {
        std::cerr << "Failed to load BPF object: errno=" << -errno << std::endl;
        bpf_object__close(obj);
        return 1;
    }

    bpf_map *rodata_map = bpf_object__find_map_by_name(obj, ".rodata");
    if (rodata_map)
    {
        size_t rodata_size = 0;
        const void *init_data = bpf_map__initial_value(rodata_map, &rodata_size);
        if (init_data && rodata_size >= sizeof(struct sched_version))
        {
            struct sched_version ebpf_ver = {};
            std::memcpy(&ebpf_ver, init_data, sizeof(ebpf_ver));
            if (ebpf_ver.output_style != static_cast<unsigned>(sched_dump_style_id()))
            {
                std::cerr << "eBPF output style mismatch. ebpf=" << output_style_name(ebpf_ver.output_style)
                          << " host=" << sched_dump_style() << std::endl;
                bpf_object__close(obj);
                return 1;
            }
        }
    }

    std::vector<bpf_link *> links;
    bpf_program *prog;
    bpf_object__for_each_program(prog, obj)
    {
        bpf_link *lnk = bpf_program__attach(prog);
        long err = libbpf_get_error(lnk);
        if (err)
        {
            const char *pname = bpf_program__name(prog);
            if (err == -ENOENT)
            {
                std::cerr << "Optional program not available: " << (pname ? pname : "?") << std::endl;
                if (lnk)
                    bpf_link__destroy(lnk);
                continue;
            }
            std::cerr << "Failed to attach program " << (pname ? pname : "?") << ": " << strerror(-err) << std::endl;
            if (lnk)
                bpf_link__destroy(lnk);
            bpf_object__close(obj);
            return 1;
        }
        links.push_back(lnk);
    }

    __u32 cfg_key = 0;
    sched_config cfg = {};
    cfg.tgid_filter_enabled = !tgid_list.empty();
    cfg.pid_filter_enabled = !pid_list.empty();
    cfg.cpu_filter_enabled = !cpu_list.empty();
    cfg.active_map = 0;
    if (bpf_map_update_elem(bpf_map__fd(cfg_map), &cfg_key, &cfg, BPF_ANY) != 0)
    {
        std::cerr << "Failed to update config_map: errno=" << errno << std::endl;
        for (bpf_link *link : links)
            bpf_link__destroy(link);
        bpf_object__close(obj);
        return 1;
    }

    for (int tgid : tgid_list)
    {
        __u32 key = static_cast<__u32>(tgid);
        __u8 val = 1;
        bpf_map_update_elem(bpf_map__fd(tgid_map), &key, &val, BPF_ANY);
    }
    for (int pid : pid_list)
    {
        __u32 key = static_cast<__u32>(pid);
        __u8 val = 1;
        bpf_map_update_elem(bpf_map__fd(pid_map), &key, &val, BPF_ANY);
    }
    for (int cpu : cpu_list)
    {
        __u32 key = static_cast<__u32>(cpu);
        __u8 val = 1;
        bpf_map_update_elem(bpf_map__fd(cpu_map), &key, &val, BPF_ANY);
    }

    signal(SIGINT, handle_sigint);
    signal(SIGTERM, handle_sigint);

    sched_dump_print_header();

    __u32 last_entry_count = 256;
    int remaining = duration_sec;
    while (!exiting && (remaining > 0 || duration_sec <= 0))
    {
        sleep(interval_sec > 0 ? interval_sec : 1);
        if (duration_sec > 0)
            remaining -= (interval_sec > 0 ? interval_sec : 1);

        int read_map = cfg.active_map;
        cfg.active_map = static_cast<__u8>(1 - cfg.active_map);
        if (bpf_map_update_elem(bpf_map__fd(cfg_map), &cfg_key, &cfg, BPF_ANY) != 0)
        {
            std::cerr << "Failed to switch active map: errno=" << errno << std::endl;
            break;
        }

        int map_fd = read_map == 0 ? bpf_map__fd(stats_map0) : bpf_map__fd(stats_map1);

        std::vector<sched_entry> entries;
        if (batch_ops_supported)
        {
            entries = collect_and_clear_batch(map_fd, last_entry_count);
            if (!batch_ops_supported)
            {
                // batch was attempted but kernel returned EINVAL – fall back
                entries = collect_stats_iter(map_fd, last_entry_count);
                clear_stats_map_iter(map_fd);
            }
        }
        else
        {
            entries = collect_stats_iter(map_fd, last_entry_count);
            clear_stats_map_iter(map_fd);
        }

        if (!entries.empty())
            last_entry_count = static_cast<__u32>(entries.size());

        sched_dump_emit(entries);
    }

    for (bpf_link *link : links)
        bpf_link__destroy(link);
    bpf_object__close(obj);
    return 0;
}
