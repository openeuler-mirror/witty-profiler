// 用户空间缓存未命中性能事件加载器

#include <bpf/bpf.h>          // BPF系统调用接口
#include <bpf/libbpf.h>       // libbpf库函数
#include <linux/perf_event.h> // Linux性能事件相关头文件
#include <signal.h>           // 信号处理
#include <sys/ioctl.h>        // I/O控制操作
#include <sys/resource.h>     // 资源限制
#include <sys/syscall.h>      // 系统调用
#include <unistd.h>           // 标准符号常量和类型

#include <cerrno>    // 错误号定义
#include <climits>   // 平台限制
#include <cstdarg>   // 可变参数处理
#include <cstdlib>   // 标准库函数
#include <cstring>   // 字符串操作
#include <iostream>  // 输入输出流
#include <string>    // 字符串类
#include <vector>    // 动态数组
#include <algorithm> // 算法库

#include "cache_miss_version.h"   // 缓存未命中版本定义
#include "dump/cache_miss_dump.h" // 缓存未命中数据导出
#include <vector>                 // 重复包含，可能是冗余

// 缓存未命中配置结构体定义
struct cache_miss_config
{
    __u32 pid;       // 目标进程ID
    __u32 tid;       // 目标线程ID
    __u32 cpu;       // 目标CPU核心
    __u8 active_map; // 活跃映射索引
    __u8 reserved1;  // 保留字段1
    __u16 reserved2; // 保留字段2
};

// 全局退出标志，用于信号处理
static volatile bool exiting = false;

/**
 * @brief libbpf日志打印回调函数
 * @param level 日志级别
 * @param fmt 格式化字符串
 * @param args 可变参数列表
 * @return 打印的字符数
 */
static int libbpf_print_fn(enum libbpf_print_level level, const char *fmt, va_list args)
{
    // 忽略调试级别日志
    if (level == LIBBPF_DEBUG)
        return 0;
    // 将日志输出到标准错误流
    return vfprintf(stderr, fmt, args);
}

/**
 * @brief 信号处理函数，设置退出标志
 * @param signum 信号编号（未使用）
 */
static void handle_sigint(int)
{
    exiting = true;
}

/**
 * @brief 提升内存锁定限制
 * @return 成功返回true，失败返回false
 */
static bool bump_memlock()
{
    struct rlimit rlim = {RLIM_INFINITY, RLIM_INFINITY}; // 设置无限内存锁定限制
    return setrlimit(RLIMIT_MEMLOCK, &rlim) == 0;        // 应用新的资源限制
}

/**
 * @brief 获取默认BPF对象文件路径
 * @return BPF对象文件的完整路径
 */
static std::string default_obj_path()
{
    char exe_path[PATH_MAX] = {0};                                            // 存储当前可执行文件路径
    ssize_t len = readlink("/proc/self/exe", exe_path, sizeof(exe_path) - 1); // 读取可执行文件符号链接
    if (len > 0)
    {
        exe_path[len] = '\0';                                           // 添加字符串结束符
        std::string exe(exe_path);                                      // 创建字符串对象
        std::string::size_type pos = exe.find_last_of('/');             // 查找最后一个路径分隔符
        if (pos != std::string::npos)                                   // 如果找到分隔符
            return exe.substr(0, pos + 1) + "cache_miss_monitor_bpf.o"; // 返回同目录下的BPF对象文件
    }
    return "cache_miss_monitor_bpf.o"; // 默认返回当前目录下的对象文件
}

/**
 * @brief 封装perf_event_open系统调用
 * @param attr 性能事件属性结构体指针
 * @param pid 目标进程ID
 * @param cpu 目标CPU核心
 * @param group_fd 事件组文件描述符
 * @param flags 标志位
 * @return 文件描述符，失败返回负值
 */
static int perf_event_open(struct perf_event_attr *attr, pid_t pid, int cpu, int group_fd, unsigned long flags)
{
    return static_cast<int>(syscall(__NR_perf_event_open, attr, pid, cpu, group_fd, flags)); // 调用系统调用
}

/**
 * @brief 显示程序使用帮助信息
 * @param prog 程序名称
 */
static void usage(const char *prog)
{
    std::cerr << "Usage: " << prog
              << " [-v] [-p pid] [-t tid] [-c cpu] [-i interval_sec] [-d duration_sec] [-s sample_period] [-o bpf_obj_path]" << std::endl;
}

/**
 * @brief 清空计数映射表中的所有元素
 * @param map_fd 映射表文件描述符
 */
static void clear_count_map(int map_fd)
{
    cache_miss_key cur_key = {};                               // 当前键值
    int res = bpf_map_get_next_key(map_fd, nullptr, &cur_key); // 获取第一个键
    while (res == 0)                                           // 遍历所有键值对
    {
        cache_miss_key next_key = {};                            // 下一个键值
        res = bpf_map_get_next_key(map_fd, &cur_key, &next_key); // 获取下一个键
        bpf_map_delete_elem(map_fd, &cur_key);                   // 删除当前元素
        if (res == 0)                                            // 如果还有下一个键
            cur_key = next_key;                                  // 更新当前键
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

/**
 * @brief 收集映射表中的计数数据
 * @param map_fd 映射表文件描述符
 * @return 缓存未命中条目向量
 */
static std::vector<cache_miss_entry> collect_counts(int map_fd)
{
    std::vector<cache_miss_entry> entries;                     // 存储结果的向量
    cache_miss_key cur_key = {};                               // 当前键值
    int res = bpf_map_get_next_key(map_fd, nullptr, &cur_key); // 获取第一个键
    while (res == 0)                                           // 遍历所有键值对
    {
        cache_miss_value count = {};                                // 计数值
        if (bpf_map_lookup_elem(map_fd, &cur_key, &count) == 0)     // 查找对应的计数值
            entries.push_back({cur_key, count.l1i, count.llc});     // 添加到结果向量

        cache_miss_key next_key = {};                            // 下一个键值
        res = bpf_map_get_next_key(map_fd, &cur_key, &next_key); // 获取下一个键
        if (res == 0)                                            // 如果还有下一个键
            cur_key = next_key;                                  // 更新当前键
    }

    // 按CPU、TGID、PID排序结果
    std::sort(entries.begin(), entries.end(), [](const cache_miss_entry &lhs, const cache_miss_entry &rhs)
              {
                  if (lhs.key.cpu != rhs.key.cpu) // 首先按CPU排序
                      return lhs.key.cpu < rhs.key.cpu;
                  if (lhs.key.tgid != rhs.key.tgid) // 然后按TGID排序
                      return lhs.key.tgid < rhs.key.tgid;
                  return lhs.key.pid < rhs.key.pid; // 最后按PID排序
              });

    return entries; // 返回排序后的结果
}

/**
 * @brief 根据样式ID获取输出样式名称
 * @param style 样式ID
 * @return 样式名称字符串
 */
static const char *output_style_name(unsigned style)
{
    return style == CACHE_MISS_OUTPUT_MSGSPEC ? "msgspec" : "csv"; // msgspec或csv格式
}

/**
 * @brief 主函数 - 缓存未命中监控程序入口点
 * @param argc 命令行参数数量
 * @param argv 命令行参数数组
 * @return 程序退出状态码
 */
int main(int argc, char **argv)
{
    std::string obj_path = default_obj_path(); // BPF对象文件路径
    int target_pid = 0;                        // 目标进程ID
    int target_tid = 0;                        // 目标线程ID
    int target_cpu = -1;                       // 目标CPU核心（-1表示所有CPU）
    int interval_sec = 1;                      // 输出间隔（秒）
    int duration_sec = 0;                      // 监控持续时间（0表示无限）
    long long sample_period = 1000;            // 采样周期（默认降低节流风险）
    bool print_version = false;                // 是否打印版本信息

    // 解析命令行参数
    int opt;
    while ((opt = getopt(argc, argv, "vp:t:c:i:d:s:o:h")) != -1)
    {
        switch (opt)
        {
        case 'v': // 版本信息选项
            print_version = true;
            break;
        case 'p': // PID选项
            target_pid = std::atoi(optarg);
            break;
        case 't': // TID选项
            target_tid = std::atoi(optarg);
            break;
        case 'c': // CPU选项
            target_cpu = std::atoi(optarg);
            break;
        case 'i': // 间隔选项
            interval_sec = std::atoi(optarg);
            break;
        case 'd': // 持续时间选项
            duration_sec = std::atoi(optarg);
            break;
        case 's': // 采样周期选项
            sample_period = std::atoll(optarg);
            break;
        case 'o': // 对象文件路径选项
            obj_path = optarg;
            break;
        case 'h': // 帮助选项
        default:  // 未知选项
            usage(argv[0]);
            return 1;
        }
    }

    // 如果请求版本信息，则打印并退出
    if (print_version)
    {
        std::cout << "output_style:" << cache_miss_dump_style()
                  << " (" << cache_miss_dump_style_id() << ")" << std::endl;
        return 0;
    }

    // 验证PID和TID参数有效性
    if (target_pid < 0 || target_tid < 0)
    {
        usage(argv[0]);
        return 1;
    }

    // 提升内存锁定限制，为BPF程序准备足够的内存
    if (!bump_memlock())
    {
        std::cerr << "Failed to raise memlock limit: " << strerror(errno) << std::endl;
        return 1;
    }

    // 设置libbpf严格模式和日志回调函数
    libbpf_set_strict_mode(LIBBPF_STRICT_ALL);
    libbpf_set_print(libbpf_print_fn);

    // 打开BPF对象文件
    bpf_object *obj = bpf_object__open_file(obj_path.c_str(), nullptr);
    if (!obj)
    {
        std::cerr << "Failed to open BPF object: " << obj_path << " errno=" << errno << std::endl;
        return 1;
    }

    // 加载BPF对象到内核
    if (bpf_object__load(obj))
    {
        std::cerr << "Failed to load BPF object: errno=" << -errno << std::endl;
        bpf_object__close(obj);
        return 1;
    }

    // 查找所需的BPF映射表
    bpf_map *cfg_map = bpf_object__find_map_by_name(obj, "config_map");    // 配置映射表
    bpf_map *count_map0 = bpf_object__find_map_by_name(obj, "count_map0"); // 计数映射表0
    bpf_map *count_map1 = bpf_object__find_map_by_name(obj, "count_map1"); // 计数映射表1
    bpf_map *drop_map = bpf_object__find_map_by_name(obj, "drop_count_map");
    if (!cfg_map || !count_map0 || !count_map1 || !drop_map)
    {
        std::cerr << "Required maps not found in BPF object" << std::endl;
        bpf_object__close(obj);
        return 1;
    }

    // 验证BPF程序的输出样式兼容性
    bpf_map *rodata_map = bpf_object__find_map_by_name(obj, ".rodata"); // 只读数据段映射
    if (rodata_map)
    {
        size_t rodata_size = 0;
        const void *init_data = bpf_map__initial_value(rodata_map, &rodata_size); // 获取初始化数据
        if (init_data && rodata_size >= sizeof(struct cache_miss_version))        // 检查数据大小
        {
            struct cache_miss_version ebpf_ver = {};                                        // eBPF版本结构体
            std::memcpy(&ebpf_ver, init_data, sizeof(ebpf_ver));                            // 复制数据
            if (ebpf_ver.output_style != static_cast<unsigned>(cache_miss_dump_style_id())) // 比较输出样式
            {
                std::cerr << "eBPF output style mismatch. ebpf=" << output_style_name(ebpf_ver.output_style)
                          << " host=" << cache_miss_dump_style() << std::endl;
                bpf_object__close(obj);
                return 1;
            }
        }
    }

    // 查找处理缓存未命中的BPF程序
    bpf_program *prog_l1i = bpf_object__find_program_by_name(obj, "handle_l1i_miss");
    bpf_program *prog_llc = bpf_object__find_program_by_name(obj, "handle_llc_miss");
    if (!prog_l1i || !prog_llc)
    {
        std::cerr << "Required programs handle_l1i_miss/handle_llc_miss not found" << std::endl;
        bpf_object__close(obj);
        return 1;
    }

    // 配置性能事件属性
    struct perf_event_attr attr_base = {};
    attr_base.type = PERF_TYPE_HW_CACHE;        // 硬件缓存事件类型
    attr_base.size = sizeof(struct perf_event_attr); // 结构体大小
    attr_base.sample_period = sample_period;    // 采样周期
    attr_base.disabled = 1;                     // 初始禁用状态
    attr_base.exclude_kernel = 0;               // 包含内核空间
    attr_base.exclude_hv = 1;                   // 排除虚拟机监控器
    attr_base.inherit = 1;                      // 子线程继承

    // 确定性能事件的目标进程ID
    int pid_for_event = -1; // 默认监控所有进程
    if (target_tid > 0)     // 如果指定TID
        pid_for_event = target_tid;
    else if (target_pid > 0) // 如果指定PID
        pid_for_event = target_pid;

    // 获取CPU核心数量
    long ncpu = sysconf(_SC_NPROCESSORS_CONF); // 查询系统配置
    if (ncpu <= 0)                             // 如果查询失败
        ncpu = 1;                              // 默认为1个CPU

    // 存储性能事件文件描述符和BPF链接
    std::vector<int> perf_fds;
    std::vector<bpf_link *> links;

    auto attach_perf = [&](bpf_program *prog, __u64 config, int cpu) -> bool {
        struct perf_event_attr attr = attr_base;
        attr.config = config;
        int perf_fd = perf_event_open(&attr, pid_for_event, cpu, -1, 0);
        if (perf_fd < 0)
        {
            std::cerr << "perf_event_open failed on cpu " << cpu << ": " << strerror(errno) << std::endl;
            return false;
        }

        bpf_link *link = bpf_program__attach_perf_event(prog, perf_fd);
        long err = libbpf_get_error(link);
        if (err)
        {
            std::cerr << "Failed to attach perf event on cpu " << cpu << ": " << strerror(-err) << std::endl;
            close(perf_fd);
            return false;
        }

        perf_fds.push_back(perf_fd);
        links.push_back(link);
        return true;
    };

    const __u64 l1i_config = PERF_COUNT_HW_CACHE_L1I |
                             (PERF_COUNT_HW_CACHE_OP_READ << 8) |
                             (PERF_COUNT_HW_CACHE_RESULT_MISS << 16);
    const __u64 llc_config = PERF_COUNT_HW_CACHE_LL |
                             (PERF_COUNT_HW_CACHE_OP_READ << 8) |
                             (PERF_COUNT_HW_CACHE_RESULT_MISS << 16);

    if (target_cpu >= 0)
    {
        if (!attach_perf(prog_l1i, l1i_config, target_cpu) ||
            !attach_perf(prog_llc, llc_config, target_cpu))
        {
            bpf_object__close(obj);
            return 1;
        }
    }
    else
    {
        for (int cpu = 0; cpu < ncpu; ++cpu)
        {
            attach_perf(prog_l1i, l1i_config, cpu);
            attach_perf(prog_llc, llc_config, cpu);
        }

        if (perf_fds.empty())
        {
            std::cerr << "Failed to attach perf events on any CPU" << std::endl;
            bpf_object__close(obj);
            return 1;
        }
    }

    // 配置BPF映射表参数
    __u32 key = 0;                                                            // 映射表键值
    cache_miss_config cfg = {};                                               // 配置结构体
    cfg.pid = static_cast<__u32>(target_pid);                                 // 设置目标PID
    cfg.tid = static_cast<__u32>(target_tid);                                 // 设置目标TID
    cfg.cpu = target_cpu >= 0 ? static_cast<__u32>(target_cpu) : 0xFFFFFFFFu; // 设置目标CPU
    cfg.active_map = 0;                                                       // 初始化活跃映射

    // 更新配置映射表
    if (bpf_map_update_elem(bpf_map__fd(cfg_map), &key, &cfg, BPF_ANY) != 0)
    {
        std::cerr << "Failed to update config_map: errno=" << errno << std::endl;
        // 清理已创建的资源
        for (bpf_link *link : links)
            bpf_link__destroy(link);
        for (int perf_fd : perf_fds)
            close(perf_fd);
        bpf_object__close(obj);
        return 1;
    }

    // 清空计数映射表
    clear_count_map(bpf_map__fd(count_map0));
    clear_count_map(bpf_map__fd(count_map1));
    reset_drop_count(bpf_map__fd(drop_map));

    // 注册信号处理函数
    signal(SIGINT, handle_sigint);  // Ctrl+C信号
    signal(SIGTERM, handle_sigint); // 终止信号

    // 启用所有性能事件
    for (int perf_fd : perf_fds)
    {
        if (ioctl(perf_fd, PERF_EVENT_IOC_RESET, 0) < 0) // 重置计数器
            std::cerr << "Failed to reset perf event: " << strerror(errno) << std::endl;
        if (ioctl(perf_fd, PERF_EVENT_IOC_ENABLE, 0) < 0) // 启用事件
        {
            std::cerr << "Failed to enable perf event: " << strerror(errno) << std::endl;
            // 清理资源并退出
            for (bpf_link *link : links)
                bpf_link__destroy(link);
            for (int fd : perf_fds)
                close(fd);
            bpf_object__close(obj);
            return 1;
        }
    }

    // 打印输出头部信息
    cache_miss_dump_print_header();

    // 主监控循环
    int remaining = duration_sec;                            // 剩余监控时间
    while (!exiting && (remaining > 0 || duration_sec == 0)) // 循环直到退出或超时
    {
        sleep(interval_sec > 0 ? interval_sec : 1);             // 等待指定间隔
        if (duration_sec > 0)                                   // 如果设置了持续时间
            remaining -= (interval_sec > 0 ? interval_sec : 1); // 减少剩余时间

        // 切换活跃映射表以实现无锁读取
        __u32 cfg_key = 0;                                      // 配置键值
        int read_map = cfg.active_map;                          // 当前读取的映射表
        cfg.active_map = static_cast<__u8>(1 - cfg.active_map); // 切换到另一个映射表
        if (bpf_map_update_elem(bpf_map__fd(cfg_map), &cfg_key, &cfg, BPF_ANY) != 0)
        {
            std::cerr << "Failed to switch active map: errno=" << errno << std::endl;
            break;
        }

        // 收集并输出计数数据
        // 选择读取映射表
        int map_fd = read_map == 0 ? bpf_map__fd(count_map0) : bpf_map__fd(count_map1);
        // 收集数据
        std::vector<cache_miss_entry> entries = collect_counts(map_fd);
        // 清空映射表
        clear_count_map(map_fd);

        __u64 drops = read_drop_count(bpf_map__fd(drop_map));
        reset_drop_count(bpf_map__fd(drop_map));
        std::clog << "[window] entries=" << entries.size() << " drops=" << drops << std::endl;

        cache_miss_dump_emit(entries); // 输出收集到的数据

        if (entries.empty() && drops == 0)
        {
            for (int perf_fd : perf_fds)
            {
                ioctl(perf_fd, PERF_EVENT_IOC_RESET, 0);
                ioctl(perf_fd, PERF_EVENT_IOC_ENABLE, 0);
            }
        }
    }

    // 禁用所有性能事件
    for (int perf_fd : perf_fds)
        ioctl(perf_fd, PERF_EVENT_IOC_DISABLE, 0);

    // 清理所有资源
    for (bpf_link *link : links)
        bpf_link__destroy(link);
    for (int perf_fd : perf_fds)
        close(perf_fd);
    bpf_object__close(obj);
    return 0;
}
