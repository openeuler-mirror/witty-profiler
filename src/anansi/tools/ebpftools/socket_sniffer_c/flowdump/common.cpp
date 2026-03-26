#include "flowdump/flowdump.h"

#include <arpa/inet.h>


const char *flow_func_name(__u8 func_id)
{
    switch (func_id)
    {
    case 1:
        return "tcp_sendmsg";
    case 2:
        return "udp_sendmsg";
    case 3:
        return "tcp_recvmsg";
    case 4:
        return "udp_recvmsg";
    default:
        return "unknown";
    }
}

std::string flow_ip_to_string(__u32 addr)
{
    struct in_addr in = {.s_addr = addr};
    char buf[INET_ADDRSTRLEN] = {0};
    const char *res = inet_ntop(AF_INET, &in, buf, sizeof(buf));
    return res ? std::string(res) : std::string("0.0.0.0");
}
