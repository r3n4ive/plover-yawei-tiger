def analyze_pinyin_map(filename, log_file="pinyin_mapping_analysis.log"):
    from collections import defaultdict

    py_to_codes = defaultdict(set)
    code_to_pys = defaultdict(set)

    # 读取映射文件
    with open(filename, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "\t" not in line:
                continue
            py, codes = line.split("\t", 1)
            codes_list = codes.split()  # 可能有多个编码用空格分隔

            for code in codes_list:
                py_to_codes[py].add(code)
                code_to_pys[code].add(py)

    # 统计一对多
    one_to_many = {py: list(codes) for py, codes in py_to_codes.items() if len(codes) > 1}

    # 统计多对一
    many_to_one = {code: list(pys) for code, pys in code_to_pys.items() if len(pys) > 1}

    # 输出日志
    with open(log_file, "w", encoding="utf-8") as log:
        log.write("=== 一对多（一个拼音 → 多个编码） ===\n")
        for py, codes in sorted(one_to_many.items()):
            log.write(f"{py} -> {' '.join(codes)}\n")

        log.write("\n=== 多对一（多个拼音 → 一个编码） ===\n")
        for code, pys in sorted(many_to_one.items()):
            log.write(f"{code} <- {' '.join(pys)}\n")

        log.write(f"\n总拼音数: {len(py_to_codes)}\n")
        log.write(f"总编码数: {len(code_to_pys)}\n")
        log.write(f"一对多数量: {len(one_to_many)}\n")
        log.write(f"多对一数量: {len(many_to_one)}\n")

    print(f"分析完成，结果已写入 {log_file}")


if __name__ == "__main__":
    analyze_pinyin_map("pinyin_to_virtual_keys.txt")

