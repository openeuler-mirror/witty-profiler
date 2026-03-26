#include "vmlinux.h"
#include "pmu_version.h"
#include "pmu_common.h"

#include <bpf/bpf_helpers.h>

struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, 1);
    __type(key, __u32);
    __type(value, struct pmu_config);
} config_map SEC(".maps");

struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, PMU_MAX_ENTRIES);
    __type(key, struct pmu_key);
    __type(value, struct pmu_value);
} pmu_map0 SEC(".maps");

struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, PMU_MAX_ENTRIES);
    __type(key, struct pmu_key);
    __type(value, struct pmu_value);
} pmu_map1 SEC(".maps");

struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, 1);
    __type(key, __u32);
    __type(value, __u64);
} drop_count_map SEC(".maps");

/* Userspace writes (sccl_id, event_type, event_code) per attached perf_event
 * into this lookup table so the BPF handler knows what each fd represents.
 * Index = perf_event attachment slot (max 256 slots). */
#define MAX_EVENT_SLOTS 256

struct event_slot {
    __u32 sccl_id;
    __u32 event_type;
    __u32 event_code;
    __u32 valid;
};

struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, MAX_EVENT_SLOTS);
    __type(key, __u32);
    __type(value, struct event_slot);
} event_slot_map SEC(".maps");

const volatile struct pmu_version pmu_ver = {
#ifdef PMU_OUTPUT_MSGSPEC
    .output_style = PMU_OUTPUT_MSGSPEC,
#else
    .output_style = PMU_OUTPUT_CSV,
#endif
    .reserved = 0,
};

static __always_inline int handle_pmu_event(struct bpf_perf_event_data *ctx,
                                            __u32 slot_idx)
{
    __u32 cfg_key = 0;
    struct pmu_config *cfg = bpf_map_lookup_elem(&config_map, &cfg_key);
    if (!cfg)
        return 0;

    struct event_slot *slot = bpf_map_lookup_elem(&event_slot_map, &slot_idx);
    if (!slot || !slot->valid)
        return 0;

    __u32 event_type = slot->event_type;

    /* Dynamic event filtering via config_map */
    if (event_type == EVENT_DDR && !cfg->enable_ddr)
        return 0;
    if (event_type == EVENT_HHA && !cfg->enable_hha)
        return 0;
    if (event_type == EVENT_L3C && !cfg->enable_l3c)
        return 0;
    if (event_type == EVENT_PA  && !cfg->enable_pa)
        return 0;

    __u32 sccl = slot->sccl_id;
    if (cfg->target_sccl != 0xFFFFFFFF && cfg->target_sccl != sccl)
        return 0;

    struct pmu_key key = {
        .sccl_id    = sccl,
        .event_type = event_type,
        .event_code = slot->event_code,
        .reserved   = 0,
    };

    void *map_ptr = &pmu_map0;
    if (cfg->active_map)
        map_ptr = &pmu_map1;

    struct pmu_value *val = bpf_map_lookup_elem(map_ptr, &key);
    __u64 now = bpf_ktime_get_ns();

    if (!val) {
        struct pmu_value new_val = {
            .count    = 1,
            .first_ts = now,
            .last_ts  = now,
        };
        if (bpf_map_update_elem(map_ptr, &key, &new_val, BPF_NOEXIST) != 0) {
            __u32 drop_key = 0;
            __u64 *drops = bpf_map_lookup_elem(&drop_count_map, &drop_key);
            if (drops)
                __sync_fetch_and_add(drops, 1);
            return 0;
        }
    } else {
        __sync_fetch_and_add(&val->count, 1);
        val->last_ts = now;
    }

    return 0;
}

/* Each perf_event fd is attached to a unique SEC("perf_event") program.
 * We use a set of handler stubs mapped to slot indices.
 * Userspace populates event_slot_map[slot_idx] before attaching.
 *
 * Generate 256 handler stubs using macro expansion.
 */

#define DEF_HANDLER(x) \
    SEC("perf_event") \
    int handle_pmu_slot_##x(struct bpf_perf_event_data *ctx) \
    { \
        return handle_pmu_event(ctx, x); \
    }

DEF_HANDLER(0)
DEF_HANDLER(1)
DEF_HANDLER(2)
DEF_HANDLER(3)
DEF_HANDLER(4)
DEF_HANDLER(5)
DEF_HANDLER(6)
DEF_HANDLER(7)
DEF_HANDLER(8)
DEF_HANDLER(9)
DEF_HANDLER(10)
DEF_HANDLER(11)
DEF_HANDLER(12)
DEF_HANDLER(13)
DEF_HANDLER(14)
DEF_HANDLER(15)
DEF_HANDLER(16)
DEF_HANDLER(17)
DEF_HANDLER(18)
DEF_HANDLER(19)
DEF_HANDLER(20)
DEF_HANDLER(21)
DEF_HANDLER(22)
DEF_HANDLER(23)
DEF_HANDLER(24)
DEF_HANDLER(25)
DEF_HANDLER(26)
DEF_HANDLER(27)
DEF_HANDLER(28)
DEF_HANDLER(29)
DEF_HANDLER(30)
DEF_HANDLER(31)
DEF_HANDLER(32)
DEF_HANDLER(33)
DEF_HANDLER(34)
DEF_HANDLER(35)
DEF_HANDLER(36)
DEF_HANDLER(37)
DEF_HANDLER(38)
DEF_HANDLER(39)
DEF_HANDLER(40)
DEF_HANDLER(41)
DEF_HANDLER(42)
DEF_HANDLER(43)
DEF_HANDLER(44)
DEF_HANDLER(45)
DEF_HANDLER(46)
DEF_HANDLER(47)
DEF_HANDLER(48)
DEF_HANDLER(49)
DEF_HANDLER(50)
DEF_HANDLER(51)
DEF_HANDLER(52)
DEF_HANDLER(53)
DEF_HANDLER(54)
DEF_HANDLER(55)
DEF_HANDLER(56)
DEF_HANDLER(57)
DEF_HANDLER(58)
DEF_HANDLER(59)
DEF_HANDLER(60)
DEF_HANDLER(61)
DEF_HANDLER(62)
DEF_HANDLER(63)
DEF_HANDLER(64)
DEF_HANDLER(65)
DEF_HANDLER(66)
DEF_HANDLER(67)
DEF_HANDLER(68)
DEF_HANDLER(69)
DEF_HANDLER(70)
DEF_HANDLER(71)
DEF_HANDLER(72)
DEF_HANDLER(73)
DEF_HANDLER(74)
DEF_HANDLER(75)
DEF_HANDLER(76)
DEF_HANDLER(77)
DEF_HANDLER(78)
DEF_HANDLER(79)
DEF_HANDLER(80)
DEF_HANDLER(81)
DEF_HANDLER(82)
DEF_HANDLER(83)
DEF_HANDLER(84)
DEF_HANDLER(85)
DEF_HANDLER(86)
DEF_HANDLER(87)
DEF_HANDLER(88)
DEF_HANDLER(89)
DEF_HANDLER(90)
DEF_HANDLER(91)
DEF_HANDLER(92)
DEF_HANDLER(93)
DEF_HANDLER(94)
DEF_HANDLER(95)
DEF_HANDLER(96)
DEF_HANDLER(97)
DEF_HANDLER(98)
DEF_HANDLER(99)
DEF_HANDLER(100)
DEF_HANDLER(101)
DEF_HANDLER(102)
DEF_HANDLER(103)
DEF_HANDLER(104)
DEF_HANDLER(105)
DEF_HANDLER(106)
DEF_HANDLER(107)
DEF_HANDLER(108)
DEF_HANDLER(109)
DEF_HANDLER(110)
DEF_HANDLER(111)
DEF_HANDLER(112)
DEF_HANDLER(113)
DEF_HANDLER(114)
DEF_HANDLER(115)
DEF_HANDLER(116)
DEF_HANDLER(117)
DEF_HANDLER(118)
DEF_HANDLER(119)
DEF_HANDLER(120)
DEF_HANDLER(121)
DEF_HANDLER(122)
DEF_HANDLER(123)
DEF_HANDLER(124)
DEF_HANDLER(125)
DEF_HANDLER(126)
DEF_HANDLER(127)
DEF_HANDLER(128)
DEF_HANDLER(129)
DEF_HANDLER(130)
DEF_HANDLER(131)
DEF_HANDLER(132)
DEF_HANDLER(133)
DEF_HANDLER(134)
DEF_HANDLER(135)
DEF_HANDLER(136)
DEF_HANDLER(137)
DEF_HANDLER(138)
DEF_HANDLER(139)
DEF_HANDLER(140)
DEF_HANDLER(141)
DEF_HANDLER(142)
DEF_HANDLER(143)
DEF_HANDLER(144)
DEF_HANDLER(145)
DEF_HANDLER(146)
DEF_HANDLER(147)
DEF_HANDLER(148)
DEF_HANDLER(149)
DEF_HANDLER(150)
DEF_HANDLER(151)
DEF_HANDLER(152)
DEF_HANDLER(153)
DEF_HANDLER(154)
DEF_HANDLER(155)
DEF_HANDLER(156)
DEF_HANDLER(157)
DEF_HANDLER(158)
DEF_HANDLER(159)
DEF_HANDLER(160)
DEF_HANDLER(161)
DEF_HANDLER(162)
DEF_HANDLER(163)
DEF_HANDLER(164)
DEF_HANDLER(165)
DEF_HANDLER(166)
DEF_HANDLER(167)
DEF_HANDLER(168)
DEF_HANDLER(169)
DEF_HANDLER(170)
DEF_HANDLER(171)
DEF_HANDLER(172)
DEF_HANDLER(173)
DEF_HANDLER(174)
DEF_HANDLER(175)
DEF_HANDLER(176)
DEF_HANDLER(177)
DEF_HANDLER(178)
DEF_HANDLER(179)
DEF_HANDLER(180)
DEF_HANDLER(181)
DEF_HANDLER(182)
DEF_HANDLER(183)
DEF_HANDLER(184)
DEF_HANDLER(185)
DEF_HANDLER(186)
DEF_HANDLER(187)
DEF_HANDLER(188)
DEF_HANDLER(189)
DEF_HANDLER(190)
DEF_HANDLER(191)
DEF_HANDLER(192)
DEF_HANDLER(193)
DEF_HANDLER(194)
DEF_HANDLER(195)
DEF_HANDLER(196)
DEF_HANDLER(197)
DEF_HANDLER(198)
DEF_HANDLER(199)
DEF_HANDLER(200)
DEF_HANDLER(201)
DEF_HANDLER(202)
DEF_HANDLER(203)
DEF_HANDLER(204)
DEF_HANDLER(205)
DEF_HANDLER(206)
DEF_HANDLER(207)
DEF_HANDLER(208)
DEF_HANDLER(209)
DEF_HANDLER(210)
DEF_HANDLER(211)
DEF_HANDLER(212)
DEF_HANDLER(213)
DEF_HANDLER(214)
DEF_HANDLER(215)
DEF_HANDLER(216)
DEF_HANDLER(217)
DEF_HANDLER(218)
DEF_HANDLER(219)
DEF_HANDLER(220)
DEF_HANDLER(221)
DEF_HANDLER(222)
DEF_HANDLER(223)
DEF_HANDLER(224)
DEF_HANDLER(225)
DEF_HANDLER(226)
DEF_HANDLER(227)
DEF_HANDLER(228)
DEF_HANDLER(229)
DEF_HANDLER(230)
DEF_HANDLER(231)
DEF_HANDLER(232)
DEF_HANDLER(233)
DEF_HANDLER(234)
DEF_HANDLER(235)
DEF_HANDLER(236)
DEF_HANDLER(237)
DEF_HANDLER(238)
DEF_HANDLER(239)
DEF_HANDLER(240)
DEF_HANDLER(241)
DEF_HANDLER(242)
DEF_HANDLER(243)
DEF_HANDLER(244)
DEF_HANDLER(245)
DEF_HANDLER(246)
DEF_HANDLER(247)
DEF_HANDLER(248)
DEF_HANDLER(249)
DEF_HANDLER(250)
DEF_HANDLER(251)
DEF_HANDLER(252)
DEF_HANDLER(253)
DEF_HANDLER(254)
DEF_HANDLER(255)

#undef DEF_HANDLER

char LICENSE[] SEC("license") = "Dual BSD/GPL";
