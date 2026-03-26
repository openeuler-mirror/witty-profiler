cmake_minimum_required(VERSION 3.15)
project(socket_sniffer_c LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

find_package(PkgConfig REQUIRED)
pkg_check_modules(LIBBPF REQUIRED libbpf)

option(SOCKET_LRU_DYNAMIC "Use dynamic LRU maps" ON)
option(SOCKET_OUTPUT_MSGSPEC "Use msgspec output" OFF)

set(BPF_C ${CMAKE_CURRENT_SOURCE_DIR}/ebpf/socket_sniffer_fixed.bpf.c)
set(BPF_OBJ ${CMAKE_CURRENT_BINARY_DIR}/socket_sniffer_bpf.o)

if (SOCKET_LRU_DYNAMIC)
    set(BPF_C ${CMAKE_CURRENT_SOURCE_DIR}/ebpf/socket_sniffer_dynamic.bpf.c)
    add_compile_definitions(LRU_DYNAMIC)
endif()

if (SOCKET_OUTPUT_MSGSPEC)
    add_compile_definitions(FLOWDUMP_MSGSPEC)
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

# Create architecture-specific directory if it doesn't exist
if (NOT EXISTS ${VMLINUX_DIR_CAND})
    file(MAKE_DIRECTORY ${VMLINUX_DIR_CAND})
endif()

# Auto-generate vmlinux.h if it doesn't exist
if (NOT EXISTS ${VMLINUX_DIR_CAND}/vmlinux.h)
    message(STATUS "vmlinux.h not found at ${VMLINUX_DIR_CAND}/vmlinux.h")
    message(STATUS "Attempting to generate vmlinux.h using bpftool...")
    
    # Check if bpftool is available
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
            message(STATUS "Please run the following command manually:")
            if (${VMLINUX_SUBDIR} STREQUAL "x86_64")
                message(STATUS "  bpftool btf dump file /sys/kernel/btf/vmlinux format c > ${VMLINUX_DIR_CAND}/vmlinux.h")
            elseif (${VMLINUX_SUBDIR} STREQUAL "aarch64")
                message(STATUS "  bpftool btf dump file /sys/kernel/btf/vmlinux format c > ${VMLINUX_DIR_CAND}/vmlinux.h")
            endif()
        endif()
    else()
        message(WARNING "bpftool not found in PATH. Please install bpftool and run:")
        if (${VMLINUX_SUBDIR} STREQUAL "x86_64")
            message(STATUS "  bpftool btf dump file /sys/kernel/btf/vmlinux format c > ${VMLINUX_DIR_CAND}/vmlinux.h")
        elseif (${VMLINUX_SUBDIR} STREQUAL "aarch64")
            message(STATUS "  bpftool btf dump file /sys/kernel/btf/vmlinux format c > ${VMLINUX_DIR_CAND}/vmlinux.h")
        endif()
    endif()
endif()

# Determine which vmlinux.h to use
if (EXISTS ${VMLINUX_DIR_CAND}/vmlinux.h)
    set(VMLINUX_DIR ${VMLINUX_DIR_CAND})
    set(VMLINUX_MSG "Using arch vmlinux.h at ${VMLINUX_DIR}/vmlinux.h")
elseif (EXISTS ${VMLINUX_FALLBACK})
    set(VMLINUX_DIR ${CMAKE_CURRENT_SOURCE_DIR})
    set(VMLINUX_MSG "Arch vmlinux.h not found; falling back to ${VMLINUX_DIR}/vmlinux.h")
else()
    message(FATAL_ERROR "vmlinux.h not found at either ${VMLINUX_DIR_CAND}/vmlinux.h or ${VMLINUX_FALLBACK}. Please generate vmlinux.h manually using bpftool.")
endif()

add_custom_command(
    OUTPUT ${BPF_OBJ}
    COMMAND ${CMAKE_COMMAND} -E echo "Building eBPF for ${CMAKE_SYSTEM_PROCESSOR} using ${BPF_TARGET_DEFINE}"
    COMMAND ${CMAKE_COMMAND} -E echo "${VMLINUX_MSG}"
    COMMAND clang -target bpf -D${BPF_TARGET_DEFINE} -O2 -g ${LIBBPF_CFLAGS} -I/usr/include -I${VMLINUX_DIR} -I${CMAKE_CURRENT_SOURCE_DIR}/ebpf -I${CMAKE_CURRENT_SOURCE_DIR} -c ${BPF_C} -o ${BPF_OBJ}
    DEPENDS ${BPF_C}
    COMMENT "Building eBPF object"
)
add_custom_target(bpf_target DEPENDS ${BPF_OBJ})

set(FLOWDUMP_SRC ${CMAKE_CURRENT_SOURCE_DIR}/flowdump/csv.cpp)
if (SOCKET_OUTPUT_MSGSPEC)
    set(FLOWDUMP_SRC ${CMAKE_CURRENT_SOURCE_DIR}/flowdump/msgspec.cpp)
endif()

set(LRU_SRC ${CMAKE_CURRENT_SOURCE_DIR}/lru/fixed.cpp)
if (SOCKET_LRU_DYNAMIC)
    set(LRU_SRC ${CMAKE_CURRENT_SOURCE_DIR}/lru/dynamic.cpp)
endif()

add_executable(socket_sniffer
    main.cpp
    flowdump/common.cpp
    ${FLOWDUMP_SRC}
    ${LRU_SRC}
)
add_dependencies(socket_sniffer bpf_target)

target_include_directories(socket_sniffer PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})

target_include_directories(socket_sniffer PRIVATE ${LIBBPF_INCLUDE_DIRS})
target_link_directories(socket_sniffer PRIVATE ${LIBBPF_LIBRARY_DIRS})
target_link_options(socket_sniffer PRIVATE ${LIBBPF_LDFLAGS})
target_link_libraries(socket_sniffer PRIVATE ${LIBBPF_LIBRARIES} elf z)

target_compile_options(socket_sniffer PRIVATE -Wall -Wextra)
