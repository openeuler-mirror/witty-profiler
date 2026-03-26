#include "sysv_sem_dump.h"
#include "sysv_sem_version.h"

#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <errno.h>
#include <limits.h>
#include <signal.h>
#include <sys/resource.h>
#include <time.h>
#include <unistd.h>

#include <algorithm>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>

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

static __u64 realtime_ns()
{
    struct timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);
    return (__u64)ts.tv_sec * 1000000000ull + (__u64)ts.tv_nsec;
}

static std::string default_obj_path()
{
    char exe_path[PATH_MAX] = {0};
    ssize_t len = readlink("/proc/self/exe", exe_path, sizeof(exe_path) - 1);
    if (len > 0) {
        exe_path[len] = '\0';
        std::string exe(exe_path);
        std::string::size_type pos = exe.find_last_of('/');
        if (pos != std::string::npos)
            return exe.substr(0, pos + 1) + "sysv_sem_bpf.o";
    }
    return "sysv_sem_bpf.o";
}

struct ipc_config {
    uint32_t target_pid;
    uint32_t target_tgid;
    uint8_t  enable_write;
    uint8_t  enable_read;
    uint8_t  active_map;
    uint8_t  reserved;
};

static int dump_sysv_sem_stats(int map_fd, int n_cpus, uint64_t window_start,
                                uint64_t window_end, bool clear_after)
{
    int entry_visited_cnt = 0;
    sysv_sem_key cur_key = {};
    std::vector<sysv_sem_stats> cpu_stats(n_cpus);

    int res = bpf_map_get_next_key(map_fd, nullptr, &cur_key);
    while (res == 0) {
        ++entry_visited_cnt;
        std::fill(cpu_stats.begin(), cpu_stats.end(), sysv_sem_stats{});
        
        if (bpf_map_lookup_elem(map_fd, &cur_key, cpu_stats.data()) == 0) {
            uint64_t count = 0;
            int16_t sem_op_val = 0;
            uint16_t sem_flg = 0;

            for (int i = 0; i < n_cpus; ++i) {
                count += cpu_stats[i].count;
                if (cpu_stats[i].count > 0) {
                    sem_op_val = cpu_stats[i].sem_op_val;
                    sem_flg = cpu_stats[i].sem_flg;
                }
            }

            if (count > 0)
                sysv_sem_dump_emit(cur_key, window_start, window_end, count, sem_op_val, sem_flg);
        }

        sysv_sem_key next_key = {};
        res = bpf_map_get_next_key(map_fd, &cur_key, &next_key);
        if (clear_after)
            bpf_map_delete_elem(map_fd, &cur_key);
        if (res == 0)
            cur_key = next_key;
    }

    return entry_visited_cnt;
}

static void usage(const char *prog)
{
    std::cerr << "Usage: " << prog 
              << " [-v]"
              << " [-p pid]"
              << " [-o bpf_obj_path]"
              << " [-i interval_sec]" 
              << std::endl;
}

int main(int argc, char **argv)
{
    std::string obj_path = default_obj_path();
    int target_pid = 0;
    int interval_sec = 1;

    bool print_version = false;
    int opt;
    while ((opt = getopt(argc, argv, "vp:o:i:")) != -1) {
        switch (opt) {
        case 'v':
            print_version = true;
            break;
        case 'p':
            target_pid = std::atoi(optarg);
            break;
        case 'o':
            obj_path = optarg;
            break;
        case 'i':
            interval_sec = std::atoi(optarg);
            break;
        default:
            usage(argv[0]);
            return 1;
        }
    }

    if (print_version) {
        std::cout << "sysv_sem_sniffer version: " 
                  << SYSV_SEM_SNIFFER_VERSION_MAJOR << "."
                  << SYSV_SEM_SNIFFER_VERSION_MINOR << "."
                  << SYSV_SEM_SNIFFER_VERSION_PATCH << std::endl;
        return 0;
    }

    if (!bump_memlock()) {
        std::cerr << "Failed to raise memlock limit: " << strerror(errno) << std::endl;
        return 1;
    }

    libbpf_set_strict_mode(LIBBPF_STRICT_ALL);
    libbpf_set_print(libbpf_print_fn);

    bpf_object *obj = bpf_object__open_file(obj_path.c_str(), nullptr);
    if (!obj) {
        std::cerr << "Failed to open BPF object: " << obj_path 
                  << " errno=" << errno << std::endl;
        return 1;
    }

    bpf_map *cfg_map = bpf_object__find_map_by_name(obj, "config_map");
    if (!cfg_map) {
        std::cerr << "Required config_map not found in object" << std::endl;
        bpf_object__close(obj);
        return 1;
    }

    if (bpf_object__load(obj)) {
        std::cerr << "Failed to load BPF object: errno=" << -errno << std::endl;
        bpf_object__close(obj);
        return 1;
    }

    std::vector<bpf_link *> links;
    bpf_program *prog;
    bpf_object__for_each_program(prog, obj) {
        bpf_link *lnk = bpf_program__attach(prog);
        long err = libbpf_get_error(lnk);
        if (err) {
            const char *pname = bpf_program__name(prog);
            if (err == -ENOENT) {
                std::clog << "[attach] optional program skipped: " 
                          << (pname ? pname : "<unknown>") << std::endl;
                continue;
            }
            std::cerr << "Failed to attach program '" 
                      << (pname ? pname : "<unknown>")
                      << "': errno=" << err << std::endl;
            for (auto *p : links)
                bpf_link__destroy(p);
            bpf_object__close(obj);
            return 1;
        }
        links.push_back(lnk);
        const char *pname = bpf_program__name(prog);
        std::clog << "[attach] program attached: " 
                  << (pname ? pname : "<unknown>") << std::endl;
    }

    int cfg_fd = bpf_map__fd(cfg_map);

    int n_cpus = libbpf_num_possible_cpus();
    if (n_cpus <= 0) {
        std::cerr << "Failed to get CPU count: " << n_cpus << std::endl;
        for (auto *p : links)
            bpf_link__destroy(p);
        bpf_object__close(obj);
        return 1;
    }

    uint32_t cfg_key = 0;
    ipc_config cfg = {};
    cfg.target_pid = static_cast<uint32_t>(target_pid);
    int active_map = 0;
    cfg.active_map = static_cast<uint8_t>(active_map);
    cfg.enable_write = 1;
    cfg.enable_read = 1;

    if (bpf_map_update_elem(cfg_fd, &cfg_key, &cfg, BPF_ANY) != 0) {
        std::cerr << "Failed to configure target pid: errno=" << errno << std::endl;
        for (auto *p : links)
            bpf_link__destroy(p);
        bpf_object__close(obj);
        return 1;
    }

    signal(SIGINT, handle_sigint);
    signal(SIGTERM, handle_sigint);

    bpf_map *stats_map_a = bpf_object__find_map_by_name(obj, "sysv_sem_stats_map_a");
    bpf_map *stats_map_b = bpf_object__find_map_by_name(obj, "sysv_sem_stats_map_b");

    sysv_sem_dump_print_header();
    uint64_t window_start = realtime_ns();

    while (!exiting) {
        uint64_t window_end = realtime_ns();
        
        int read_map = active_map;
        active_map = 1 - active_map;
        cfg.active_map = static_cast<uint8_t>(active_map);
        
        if (bpf_map_update_elem(cfg_fd, &cfg_key, &cfg, BPF_ANY) != 0) {
            std::cerr << "Failed to switch active map: errno=" << errno << std::endl;
            break;
        }

        int stats_fd = bpf_map__fd(read_map == 0 ? stats_map_a : stats_map_b);
        int entry_cnt = dump_sysv_sem_stats(stats_fd, n_cpus, window_start, window_end, true);

        std::clog << "[map:" << read_map << "] entry usage: " << entry_cnt << std::endl;

        window_start = window_end;
        sleep(interval_sec > 0 ? interval_sec : 1);
    }

    for (auto *p : links)
        bpf_link__destroy(p);
    bpf_object__close(obj);
    return 0;
}
