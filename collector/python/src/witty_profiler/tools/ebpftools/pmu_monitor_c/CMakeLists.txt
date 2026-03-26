cmake_minimum_required(VERSION 3.15)
project(pmu_monitor_c LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

find_package(PkgConfig REQUIRED)
pkg_check_modules(LIBBPF REQUIRED libbpf)

option(PMU_OUTPUT_MSGSPEC "Use msgspec output" OFF)

set(BPF_C ${CMAKE_CURRENT_SOURCE_DIR}/ebpf/pmu_monitor.bpf.c)
set(BPF_OBJ ${CMAKE_CURRENT_BINARY_DIR}/pmu_monitor_bpf.o)

set(BPF_DEFINES "")
if (PMU_OUTPUT_MSGSPEC)
    add_compile_definitions(PMU_OUTPUT_MSGSPEC)
    set(BPF_DEFINES "-DPMU_OUTPUT_MSGSPEC")
endif()

# Detect architecture and set BPF target macro and vmlinux.h include dir
string(TOLOWER "${CMAKE_SYSTEM_PROCESSOR}" SYS_PROC_LOWER)
set(BPF_TARGET_DEFINE "__TARGET_ARCH_x86")
set(VMLINUX_SUBDIR "x86_64")

if (SYS_PROC_LOWER MATCHES "x86_64|amd64")
    set(BPF_TARGET_DEFINE "__TARGET_ARCH_x86")
    set(VMLINUX_SUBDIR "x86_64")
elseif (SYS_PROC_LOWER MATCHES "aarch64|arm64")
    set(BPF_TARGET_DEFINE "__TARGET_ARCH_arm64")
    set(VMLINUX_SUBDIR "aarch64")
elseif (SYS_PROC_LOWER MATCHES "armv7|armv6|arm")
    set(BPF_TARGET_DEFINE "__TARGET_ARCH_arm")
    set(VMLINUX_SUBDIR "arm")
elseif (SYS_PROC_LOWER MATCHES "riscv64|riscv")
    set(BPF_TARGET_DEFINE "__TARGET_ARCH_riscv")
    set(VMLINUX_SUBDIR "riscv64")
endif()

set(VMLINUX_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/../vmlinux)
set(VMLINUX_DIR_CAND ${VMLINUX_ROOT}/${VMLINUX_SUBDIR})
set(VMLINUX_FALLBACK ${VMLINUX_ROOT}/vmlinux.h)

if (NOT EXISTS ${VMLINUX_DIR_CAND})
    file(MAKE_DIRECTORY ${VMLINUX_DIR_CAND})
endif()

if (NOT EXISTS ${VMLINUX_DIR_CAND}/vmlinux.h)
    message(STATUS "vmlinux.h not found at ${VMLINUX_DIR_CAND}/vmlinux.h")
    message(STATUS "Attempting to generate vmlinux.h using bpftool...")
    find_program(BPFTOOL_EXECUTABLE bpftool)
    if (BPFTOOL_EXECUTABLE)
        execute_process(
            COMMAND ${BPFTOOL_EXECUTABLE} btf dump file /sys/kernel/btf/vmlinux format c
            OUTPUT_FILE ${VMLINUX_DIR_CAND}/vmlinux.h
            RESULT_VARIABLE BPFTOOL_RESULT
        )
        if (BPFTOOL_RESULT EQUAL 0)
            message(STATUS "Successfully generated vmlinux.h at ${VMLINUX_DIR_CAND}/vmlinux.h")
        else()
            message(WARNING "Failed to generate vmlinux.h using bpftool (error code: ${BPFTOOL_RESULT})")
        endif()
    else()
        message(WARNING "bpftool not found in PATH. Please install bpftool and run:")
        message(STATUS "  bpftool btf dump file /sys/kernel/btf/vmlinux format c > ${VMLINUX_DIR_CAND}/vmlinux.h")
    endif()
endif()

if (EXISTS ${VMLINUX_DIR_CAND}/vmlinux.h)
    set(VMLINUX_DIR ${VMLINUX_DIR_CAND})
    set(VMLINUX_MSG "Using arch vmlinux.h at ${VMLINUX_DIR}/vmlinux.h")
elseif (EXISTS ${VMLINUX_FALLBACK})
    set(VMLINUX_DIR ${CMAKE_CURRENT_SOURCE_DIR})
    set(VMLINUX_MSG "Arch vmlinux.h not found; falling back to ${VMLINUX_DIR}/vmlinux.h")
else()
    message(FATAL_ERROR "vmlinux.h not found. Please generate it with bpftool.")
endif()

add_custom_command(
    OUTPUT ${BPF_OBJ}
    COMMAND ${CMAKE_COMMAND} -E echo "Building eBPF for ${CMAKE_SYSTEM_PROCESSOR} using ${BPF_TARGET_DEFINE}"
    COMMAND ${CMAKE_COMMAND} -E echo "${VMLINUX_MSG}"
    COMMAND clang -target bpf -D${BPF_TARGET_DEFINE} ${BPF_DEFINES} -O2 -g ${LIBBPF_CFLAGS} -I/usr/include -I${VMLINUX_DIR} -I${CMAKE_CURRENT_SOURCE_DIR}/ebpf -I${CMAKE_CURRENT_SOURCE_DIR} -c ${BPF_C} -o ${BPF_OBJ}
    DEPENDS ${BPF_C}
    COMMENT "Building eBPF object"
)
add_custom_target(bpf_target DEPENDS ${BPF_OBJ})

set(PMU_DUMP_SRC ${CMAKE_CURRENT_SOURCE_DIR}/dump/csv.cpp)
if (PMU_OUTPUT_MSGSPEC)
    set(PMU_DUMP_SRC ${CMAKE_CURRENT_SOURCE_DIR}/dump/msgspec.cpp)
endif()

add_executable(pmu_monitor
    main.cpp
    ${PMU_DUMP_SRC}
)
add_dependencies(pmu_monitor bpf_target)

target_include_directories(pmu_monitor PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})

target_include_directories(pmu_monitor PRIVATE ${LIBBPF_INCLUDE_DIRS})
target_link_directories(pmu_monitor PRIVATE ${LIBBPF_LIBRARY_DIRS})
target_link_options(pmu_monitor PRIVATE ${LIBBPF_LDFLAGS})
target_link_libraries(pmu_monitor PRIVATE ${LIBBPF_LIBRARIES} elf z)

target_compile_options(pmu_monitor PRIVATE -Wall -Wextra)
