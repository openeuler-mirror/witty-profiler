cmake_minimum_required(VERSION 3.15)
project(sysv_sem_sniffer LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

find_package(PkgConfig REQUIRED)
pkg_check_modules(LIBBPF REQUIRED libbpf)

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
    find_program(BPFTOOL_EXECUTABLE bpftool)
    if (BPFTOOL_EXECUTABLE)
        execute_process(
            COMMAND ${BPFTOOL_EXECUTABLE} btf dump file /sys/kernel/btf/vmlinux format c
            OUTPUT_FILE ${VMLINUX_DIR_CAND}/vmlinux.h
            RESULT_VARIABLE BPFTOOL_RESULT
        )
    endif()
endif()

if (EXISTS ${VMLINUX_DIR_CAND}/vmlinux.h)
    set(VMLINUX_DIR ${VMLINUX_DIR_CAND})
elseif (EXISTS ${VMLINUX_FALLBACK})
    set(VMLINUX_DIR ${CMAKE_CURRENT_SOURCE_DIR}/..)
else()
    message(FATAL_ERROR "vmlinux.h not found. Please generate it using bpftool.")
endif()

set(IPC_COMMON_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../ipc_common)

set(BPF_C ${CMAKE_CURRENT_SOURCE_DIR}/ebpf/sysv_sem.bpf.c)
set(BPF_OBJ ${CMAKE_CURRENT_BINARY_DIR}/sysv_sem_bpf.o)

add_custom_command(
    OUTPUT ${BPF_OBJ}
    COMMAND clang -target bpf -D${BPF_TARGET_DEFINE} -O2 -g ${LIBBPF_CFLAGS}
            -I/usr/include -I${VMLINUX_DIR} -I${CMAKE_CURRENT_SOURCE_DIR}/ebpf
            -I${IPC_COMMON_DIR} -c ${BPF_C} -o ${BPF_OBJ}
    DEPENDS ${BPF_C}
    COMMENT "Building eBPF object"
)
add_custom_target(bpf_target DEPENDS ${BPF_OBJ})

add_executable(sysv_sem_sniffer main.cpp dump/csv.cpp)
add_dependencies(sysv_sem_sniffer bpf_target)

target_include_directories(sysv_sem_sniffer PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
target_include_directories(sysv_sem_sniffer PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/dump)
target_include_directories(sysv_sem_sniffer PRIVATE ${IPC_COMMON_DIR})
target_include_directories(sysv_sem_sniffer PRIVATE ${LIBBPF_INCLUDE_DIRS})
target_link_directories(sysv_sem_sniffer PRIVATE ${LIBBPF_LIBRARY_DIRS})
target_link_options(sysv_sem_sniffer PRIVATE ${LIBBPF_LDFLAGS})
target_link_libraries(sysv_sem_sniffer PRIVATE ${LIBBPF_LIBRARIES} elf z)

target_compile_options(sysv_sem_sniffer PRIVATE -Wall -Wextra)
