#pragma once

// 定义一个函数 flow_dump_style 以备打印 和 查询对比
// 具体实现由 csv.cpp 或 msgspec.cpp 文件完成

const char *flow_dump_style();
int flow_dump_style_id();

enum FlowDumpStyleId
{
	FLOW_DUMP_STYLE_CSV = 1,
	FLOW_DUMP_STYLE_MSGSPEC = 2,
};