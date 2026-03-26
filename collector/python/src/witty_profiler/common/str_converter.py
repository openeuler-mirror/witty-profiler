def list_to_range_str(cpu_list: list[int]) -> str:
    # [1,2,3,5] → "1-3,5"
    cpu_list = sorted(cpu_list)
    L = len(cpu_list)
    if L == 0:
        return ""
    ranges_str = []
    last_start = cpu_list[0]
    last_end = cpu_list[0]
    for i, cpu in enumerate(cpu_list):
        if cpu > last_end + 1:
            ranges_str.append(
                f"{last_start}-{last_end}"
                if last_start != last_end
                else str(last_start)
            )
            last_start = cpu
            last_end = cpu
        else:
            last_end = cpu
    ranges_str.append(
        f"{last_start}-{last_end}" if last_start != last_end else str(last_start)
    )
    return ",".join(ranges_str)


def range_str_to_list(s: str) -> list[int]:
    ans = set()
    for cpu_range in s.split(","):
        cpu_range = cpu_range.strip().split("-")
        if len(cpu_range) == 1:
            if cpu_range[0] == "":
                continue
            ans.add(int(cpu_range[0]))
        elif len(cpu_range) == 2:
            ans.update(range(int(cpu_range[0]), int(cpu_range[1]) + 1))
        else:
            raise ValueError(f"Invalid range: {cpu_range}")
    return list(ans)
