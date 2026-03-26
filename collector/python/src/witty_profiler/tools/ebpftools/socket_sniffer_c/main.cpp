// User-space loader for the eBPF flow stats collector.

#include "flow_types.h"
#include "flowdump/flowdump.h"
#include "flowdump/flow_dump_version.h"
#include "lru/lru_map.h"
#include "lru/lru_version.h"
#include "ebpf/socket_sniffer_version.h"


#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <errno.h>
#include <limits>
#include <signal.h>
#include <sys/resource.h>
#include <time.h>
#include <unistd.h>

#include <algorithm>
#include <climits>
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
    if (len > 0)
    {
        exe_path[len] = '\0';
        std::string exe(exe_path);
        std::string::size_type pos = exe.find_last_of('/');
        if (pos != std::string::npos)
            return exe.substr(0, pos + 1) + "socket_sniffer_bpf.o";
    }
    return "socket_sniffer_bpf.o";
}

static int dump_flows(int map_fd, int n_cpus, __u64 window_start, __u64 window_end, bool clear_after)
{
    int entry_visited_cnt = 0;
    flow_key cur_key = {};
    std::vector<flow_stats_val> cpu_stats(n_cpus);

    int res = bpf_map_get_next_key(map_fd, nullptr, &cur_key);
    while (res == 0)
    {
        ++entry_visited_cnt;
        std::fill(cpu_stats.begin(), cpu_stats.end(), flow_stats_val{});
        if (bpf_map_lookup_elem(map_fd, &cur_key, cpu_stats.data()) == 0)
        {
            __u64 bytes = 0;
            __u64 pkts = 0;
            __u64 start_ns = std::numeric_limits<__u64>::max();
            __u64 end_ns = 0;

            for (int i = 0; i < n_cpus; ++i)
            {
                bytes += cpu_stats[i].bytes;
                pkts += cpu_stats[i].pkts;
                if (cpu_stats[i].bytes)
                {
                    if (cpu_stats[i].start_ns < start_ns)
                        start_ns = cpu_stats[i].start_ns;
                    if (cpu_stats[i].end_ns > end_ns)
                        end_ns = cpu_stats[i].end_ns;
                }
            }

            if (bytes)
                flowdump_emit(cur_key, window_start, window_end, bytes, pkts);
        }

        flow_key next_key = {};
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
        <<" [-p pid]"
        <<" [-o bpf_obj_path]"
        <<" [-d send|recv|all]"
        <<" [-m max_lru_entries]"
        <<" [-i interval_sec]" 
        <<" [-c]" 
        << std::endl;
}


/**
 * @brief 主循环函数，用于周期性地切换活跃映射、读取统计信息并输出流量数据
 * 
 * 该函数实现了一个持续运行的主循环，负责管理双缓冲映射的切换，读取网络流统计数据，
 * 并定期输出当前映射的使用情况和流量信息。
 * 
 * @param cfg_fd 配置映射的文件描述符，用于更新配置信息
 * @param active_map 当前活跃映射的索引（0或1），在循环中会被切换
 * @param cfg 配置结构体引用，包含当前的配置信息
 * @param n_cpus CPU数量，用于dump_flows函数处理多CPU数据
 * @param interval_sec 循环间隔时间（秒），控制数据采集频率
 * @param lru LRU状态指针，管理映射的LRU操作和大小调整
 */
static void main_loop(int cfg_fd, int &active_map, config &cfg, int n_cpus, int interval_sec, LruState *lru)
{
    __u32 cfg_key = 0;
    __u64 window_start = realtime_ns();

    // 主循环：持续运行直到exiting标志被设置
    while (!exiting)
    {
        __u64 window_end = realtime_ns();
        
        // 保存当前要读取的映射索引，并切换活跃映射
        int read_map = active_map;
        active_map = 1 - active_map;
        cfg.active_map = static_cast<__u8>(active_map);
        
        // 更新BPF映射中的配置信息，通知内核切换活跃映射
        if (bpf_map_update_elem(cfg_fd, &cfg_key, &cfg, BPF_ANY) != 0)
        {
            std::cerr << "Failed to switch active map: errno=" << errno << std::endl;
            break;
        }

        // 获取要读取的统计信息文件描述符并输出流量数据
        int stats_fd = lru_read_fd(lru, read_map);
        int entry_cnt = dump_flows(stats_fd, n_cpus, window_start, window_end, true);

        // 输出当前映射的使用统计信息
        int map_size = lru->map_sizes[read_map];
        std::clog << "[map:" << read_map << "]entry usage: " << entry_cnt << "/" << map_size
                  << " (" << (entry_cnt * 100 / map_size) << "%)" << std::endl;
                  
        // 根据当前条目数量可能调整映射大小
        lru_maybe_resize(lru, read_map, entry_cnt);

        // 更新时间窗口起点并休眠指定间隔
        window_start = window_end;
        sleep(interval_sec > 0 ? interval_sec : 1);
    }
}

int main(int argc, char **argv)
{
    std::string obj_path = default_obj_path();
    int target_pid = 0;
    std::string direction = "all";
    int interval_sec = 1;

    int max_lru_entries = 10240;
    int min_lru_entries = 1024;

    bool print_version = false;
    int compress_msg = 0;
    int opt;
    while ((opt = getopt(argc, argv, "vp:o:d:m:i:c")) != -1)
    {
        switch (opt)
        {
        case 'v':
            print_version = true;
            break;
        case 'p':
            target_pid = std::atoi(optarg);
            break;
        case 'o':
            obj_path = optarg;
            break;
        case 'd':
            direction = optarg;
            break;
        case 'm':
            max_lru_entries = std::atoi(optarg);
            break;
        case 'i':
            interval_sec = std::atoi(optarg);
            break;
        case 'c':
            compress_msg = 1;
            break;
        default:
            usage(argv[0]);
            return 1;
        }
    }

    if (print_version)
    {
        std::cout << "lru_style:" << get_lru_style() << " (" << get_lru_style_id() << ")" << std::endl;
        std::cout << "flow_dump_style:" << flow_dump_style() << " (" << flow_dump_style_id() << ")" << std::endl;
        return 0;
    }
    

#if defined(LRU_DYNAMIC)
    if (max_lru_entries < (min_lru_entries << 3))
        std::cerr << "max_lru_entries must be greater than or equal to " << (min_lru_entries << 3) << std::endl;
#endif

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
    if (!cfg_map)
    {
        std::cerr << "Required config_map not found in object" << std::endl;
        bpf_object__close(obj);
        return 1;
    }

    bpf_map *rodata_map = bpf_object__find_map_by_name(obj, ".rodata");
    if (rodata_map)
    {
        size_t rodata_size = 0;
        const void *init_data = bpf_map__initial_value(rodata_map, &rodata_size);
        if (init_data && rodata_size >= sizeof(struct socket_sniffer_version))
        {
            struct socket_sniffer_version ebpf_ver = {};
            std::memcpy(&ebpf_ver, init_data, sizeof(ebpf_ver));
            if (static_cast<int>(ebpf_ver.lru_style) != get_lru_style_id())
            {
                std::cerr << "eBPF LRU style mismatch. ebpf=" << ebpf_ver.lru_style
                          << " host=" << get_lru_style_id() << std::endl;
                bpf_object__close(obj);
                return 1;
            }
        }
    }

    LruState lru = {};
    if (!lru_prepare(obj, max_lru_entries, min_lru_entries, &lru))
    {
        std::cerr << "Failed to prepare LRU maps" << std::endl;
        bpf_object__close(obj);
        return 1;
    }

    if (bpf_object__load(obj))
    {
        std::cerr << "Failed to load BPF object: errno=" << -errno << std::endl;
        lru_cleanup(&lru);
        bpf_object__close(obj);
        return 1;
    }



    if (!lru_after_load(obj, &lru))
    {
        std::cerr << "Failed to finalize LRU maps" << std::endl;
        lru_cleanup(&lru);
        bpf_object__close(obj);
        return 1;
    }

    bpf_program *prog;
    std::vector<bpf_link *> links;
    bpf_object__for_each_program(prog, obj)
    {
        bpf_link *lnk = bpf_program__attach(prog);
        long err = libbpf_get_error(lnk);
        if (err)
        {
            const char *pname = bpf_program__name(prog);
            // Treat missing kprobe symbols as optional and continue.
            if (err == -ENOENT)
            {
                std::clog << "[attach] optional program skipped: " << (pname ? pname : "<unknown>") << std::endl;
                continue;
            }
            std::cerr << "Failed to attach program '" << (pname ? pname : "<unknown>")
                      << "': errno=" << err << std::endl;
            for (auto *p : links)
                bpf_link__destroy(p);
            lru_cleanup(&lru);
            bpf_object__close(obj);
            return 1;
        }
        links.push_back(lnk);
        const char *pname = bpf_program__name(prog);
        std::clog << "[attach] program attached: " << (pname ? pname : "<unknown>") << std::endl;
    }

    int cfg_fd = bpf_map__fd(cfg_map);

    int n_cpus = libbpf_num_possible_cpus();
    if (n_cpus <= 0)
    {
        std::cerr << "Failed to get CPU count: " << n_cpus << std::endl;
        for (auto *p : links)
            bpf_link__destroy(p);
        lru_cleanup(&lru);
        bpf_object__close(obj);
        return 1;
    }

    __u32 cfg_key = 0;
    config cfg = {};
    cfg.target_pid = static_cast<__u32>(target_pid);
    int active_map = 0;
    cfg.active_map = static_cast<__u8>(active_map);
    if (direction == "send")
    {
        cfg.enable_send = 1;
        cfg.enable_recv = 0;
    }
    else if (direction == "recv")
    {
        cfg.enable_send = 0;
        cfg.enable_recv = 1;
    }
    else
    {
        cfg.enable_send = 1;
        cfg.enable_recv = 1;
    }
    cfg.compress_msg = compress_msg;

    if (bpf_map_update_elem(cfg_fd, &cfg_key, &cfg, BPF_ANY) != 0)
    {
        std::cerr << "Failed to configure target pid: errno=" << errno << std::endl;
        for (auto *p : links)
            bpf_link__destroy(p);
        lru_cleanup(&lru);
        bpf_object__close(obj);
        return 1;
    }

    signal(SIGINT, handle_sigint);
    signal(SIGTERM, handle_sigint);

    flowdump_print_header();
    // 循环导出
    main_loop(cfg_fd, active_map, cfg, n_cpus, interval_sec, &lru);

    for (auto *p : links)
        bpf_link__destroy(p);
    lru_cleanup(&lru);
    bpf_object__close(obj);
    return 0;
}
