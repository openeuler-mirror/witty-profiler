#pragma once

/* Huawei Kunpeng 920 uncore PMU event codes.
 * Source: local/report/hccs_profiling/pmu_events_reference.md
 *         Linux kernel drivers/perf/hisilicon/
 * PMU devices discovered via /sys/devices/hisi_sccl*_*
 * sysfs type used with perf_event_open; config = event code below */

/* DDR Controller (DDRC) events */
#define HISI_DDRC_FLUX_WR        0x83  /* write flux (count * 32B = bytes) */
#define HISI_DDRC_FLUX_RD        0x84  /* read flux  (count * 32B = bytes) */

/* HHA (Hyper Home Agent) events */
#define HISI_HHA_RX_OPS_NUM      0x00
#define HISI_HHA_RX_OUTER        0x01  /* cross-socket operations */
#define HISI_HHA_RX_SCCL         0x02  /* cross-die operations */
#define HISI_HHA_RD_DDR_64B      0x1C
#define HISI_HHA_WR_DDR_64B      0x1D
#define HISI_HHA_RD_DDR_128B     0x1E
#define HISI_HHA_WR_DDR_128B     0x1F

/* L3C (L3 Cache) events */
#define HISI_L3C_RD_CPIPE        0x00
#define HISI_L3C_WR_CPIPE        0x01
#define HISI_L3C_RD_HIT_CPIPE    0x02
#define HISI_L3C_WR_HIT_CPIPE    0x03
#define HISI_L3C_VICTIM_CNT      0x0F
#define HISI_L3C_RD_SPIPE        0x20
#define HISI_L3C_WR_SPIPE        0x21
#define HISI_L3C_RD_HIT_SPIPE    0x22
#define HISI_L3C_WR_HIT_SPIPE    0x23
#define HISI_L3C_BACK_INV_NUM    0x48
#define HISI_L3C_RETRY_REQ       0xB8

/* PA (Port Agent / HCCS link) - ring-to-PA flit counts */
#define HISI_PA_RING2PA_LINK0    0x40
#define HISI_PA_RING2PA_LINK1    0x44
#define HISI_PA_RING2PA_LINK2    0x48
#define HISI_PA_RING2PA_LINK3    0x4C

/* PA-to-Ring flit counts */
#define HISI_PA_PA2RING_LINK0    0x50
#define HISI_PA_PA2RING_LINK1    0x54
#define HISI_PA_PA2RING_LINK2    0x58
#define HISI_PA_PA2RING_LINK3    0x5C

#define HISI_PA_CYCLES           0x78

/* Bandwidth calculation: count * BYTES_PER_COUNT / interval_sec / 1e9 = GB/s */
#define HISI_DDR_BYTES_PER_COUNT    32
#define HISI_L3C_BYTES_PER_COUNT    64
#define HISI_HHA_64B_ACCESS_SIZE    64
#define HISI_HHA_128B_ACCESS_SIZE   128
#define HISI_PA_BW_FACTOR           30   /* flit/cycle * 30 = GB/s */
