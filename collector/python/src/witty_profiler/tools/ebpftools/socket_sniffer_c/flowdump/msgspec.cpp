#include "flowdump/flowdump.h"
#include "flowdump/flow_dump_version.h"

#include <cstdint>
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

static void mp_write_str(std::string &buf, const std::string &s)
{
    const size_t len = s.size();
    if (len <= 31)
    {
        buf.push_back(static_cast<char>(0xa0 | static_cast<__u8>(len)));
    }
    else if (len <= 0xff)
    {
        buf.push_back(static_cast<char>(0xd9));
        buf.push_back(static_cast<char>(len & 0xFF));
    }
    else if (len <= 0xffff)
    {
        buf.push_back(static_cast<char>(0xda));
        append_u16_be(buf, static_cast<__u16>(len));
    }
    else
    {
        buf.push_back(static_cast<char>(0xdb));
        append_u32_be(buf, static_cast<__u32>(len));
    }
    buf.append(s.data(), s.size());
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

void flowdump_print_header()
{
}

void flowdump_emit(const flow_key &key,
                   __u64 window_start,
                   __u64 window_end,
                   __u64 bytes,
                   __u64 pkts)
{
    std::string payload;
    payload.reserve(256);

    mp_write_array_header(payload, 11);
    mp_write_str(payload, flow_func_name(key.func_id));
    mp_write_uint(payload, key.pid);
    mp_write_uint(payload, key.tid);
    mp_write_str(payload, flow_ip_to_string(key.saddr));
    mp_write_uint(payload, key.sport);
    mp_write_str(payload, flow_ip_to_string(key.daddr));
    mp_write_uint(payload, key.dport);
    mp_write_uint(payload, window_start);
    mp_write_uint(payload, window_end);
    mp_write_uint(payload, bytes);
    mp_write_uint(payload, pkts);

    std::string frame;
    frame.reserve(4 + payload.size());
    append_u32_be(frame, static_cast<__u32>(payload.size()));
    frame.append(payload);

    std::cout.write(frame.data(), static_cast<std::streamsize>(frame.size()));
    std::cout.flush();
}

const char *flow_dump_style()
{
    return "msgspec";
}

int flow_dump_style_id()
{
    return FLOW_DUMP_STYLE_MSGSPEC;
}
