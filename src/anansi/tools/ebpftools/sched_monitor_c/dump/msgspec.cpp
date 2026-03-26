#include "dump/sched_dump.h"

#include <iostream>
#include <string>

static void append_u16_be(std::string &buf, __u16 v)
{
    buf.push_back(static_cast<char>((v >> 8) & 0xFF));
    buf.push_back(static_cast<char>(v & 0xFF));
}

static void append_u32_be(std::string &buf, __u32 v)
{
    buf.push_back(static_cast<char>((v >> 24) & 0xFF));
    buf.push_back(static_cast<char>((v >> 16) & 0xFF));
    buf.push_back(static_cast<char>((v >> 8) & 0xFF));
    buf.push_back(static_cast<char>(v & 0xFF));
}

static void append_u64_be(std::string &buf, __u64 v)
{
    buf.push_back(static_cast<char>((v >> 56) & 0xFF));
    buf.push_back(static_cast<char>((v >> 48) & 0xFF));
    buf.push_back(static_cast<char>((v >> 40) & 0xFF));
    buf.push_back(static_cast<char>((v >> 32) & 0xFF));
    buf.push_back(static_cast<char>((v >> 24) & 0xFF));
    buf.push_back(static_cast<char>((v >> 16) & 0xFF));
    buf.push_back(static_cast<char>((v >> 8) & 0xFF));
    buf.push_back(static_cast<char>(v & 0xFF));
}

static void mp_write_uint(std::string &buf, __u64 v)
{
    if (v <= 0x7f)
    {
        buf.push_back(static_cast<char>(v));
    }
    else if (v <= 0xff)
    {
        buf.push_back(static_cast<char>(0xcc));
        buf.push_back(static_cast<char>(v & 0xFF));
    }
    else if (v <= 0xffff)
    {
        buf.push_back(static_cast<char>(0xcd));
        append_u16_be(buf, static_cast<__u16>(v));
    }
    else if (v <= 0xffffffff)
    {
        buf.push_back(static_cast<char>(0xce));
        append_u32_be(buf, static_cast<__u32>(v));
    }
    else
    {
        buf.push_back(static_cast<char>(0xcf));
        append_u64_be(buf, v);
    }
}

static void mp_write_array_header(std::string &buf, __u32 size)
{
    if (size <= 15)
    {
        buf.push_back(static_cast<char>(0x90 | static_cast<__u8>(size)));
    }
    else
    {
        buf.push_back(static_cast<char>(0xdc));
        append_u16_be(buf, static_cast<__u16>(size));
    }
}

void sched_dump_print_header()
{
}

void sched_dump_emit(const std::vector<sched_entry> &entries)
{
    for (const auto &entry : entries)
    {
        std::string payload;
        payload.reserve(64);

        mp_write_array_header(payload, 4);
        mp_write_uint(payload, entry.key.pid);
        mp_write_uint(payload, entry.key.tgid);
        mp_write_uint(payload, entry.key.cpu);
        mp_write_uint(payload, entry.time_ns);

        std::string frame;
        frame.reserve(4 + payload.size());
        append_u32_be(frame, static_cast<__u32>(payload.size()));
        frame.append(payload);

        std::cout.write(frame.data(), static_cast<std::streamsize>(frame.size()));
    }
    std::cout.flush();
}

const char *sched_dump_style()
{
    return "msgspec";
}

int sched_dump_style_id()
{
    return SCHED_OUTPUT_MSGSPEC;
}
