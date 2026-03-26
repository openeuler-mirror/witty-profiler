#pragma once

// 定义一个函数 get_lru_style 以备打印 和 查询对比
// 具体实现由 不同的.cpp 文件完成

const char *get_lru_style();
int get_lru_style_id();

enum LruStyleId
{
	LRU_STYLE_FIXED = 1,
	LRU_STYLE_DYNAMIC = 2,
};