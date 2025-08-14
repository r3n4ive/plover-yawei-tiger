import itertools

# 文件路径
fixed_file = "fixed.dict"
pinyin_map_file = "../theory_map/pinyin_to_virtual_keys.txt"
base_file = "../base/base.dict.yaml"
output_file = "root_filter.txt.temp"

# 读取 fixed.dict 中 type=root 的项
fixed_roots = {}
with open(fixed_file, "r", encoding="utf-8") as f:
    for line in f:
        if not line.strip():
            continue
        word, code, ctype = line.strip().split("\t")
        if ctype == "root":
            fixed_roots[word] = code

# 读取拼音到虚拟键位映射（一个拼音可能对应多个编码）
pinyin_map = {}
with open(pinyin_map_file, "r", encoding="utf-8") as f:
    for line in f:
        if not line.strip():
            continue
        parts = line.strip().split("\t")
        if len(parts) != 2:
            continue
        pinyin, vk = parts
        pinyin_map.setdefault(pinyin, []).append(vk)

results = []

# 处理 base.dict.yaml
with open(base_file, "r", encoding="utf-8") as f:
    for line in f:
        if not line.strip() or line.startswith("#"):
            continue
        line_split = line.strip().split("\t")
        if len(line_split) != 3:
            continue
        word, pinyin_str, freq = line_split
        pinyin_list = pinyin_str.split()

        # 判断是否包含 fixed 中的 root 词
        contains_root = False
        for root_word in fixed_roots:
            if root_word in word:
                contains_root = True
                break

        if not contains_root:
            continue  # 跳过不包含 root 的

        # 生成编码组合
        code_options = []
        for char, pinyin in zip(word, pinyin_list):
            if char in fixed_roots:
                # 如果该字在 fixed_roots 里，用固定编码
                code_options.append([fixed_roots[char]])
            elif pinyin in pinyin_map:
                # 否则用拼音映射的所有编码
                code_options.append(pinyin_map[pinyin])
            else:
                # 没有映射的跳过
                code_options.append(["??"])

        # 笛卡尔积生成所有组合，使用 - / 交替拼接
        for combo in itertools.product(*code_options):
            parts_joined = combo[0]
            sep = "-"
            for part in combo[1:]:
                parts_joined += sep + part
                sep = "/" if sep == "-" else "-"
            results.append(f"{word}\t{parts_joined}\t{freq}")

# 输出结果
with open(output_file, "w", encoding="utf-8") as f:
    for line in results:
        f.write(line + "\n")

print(f"生成完成，共 {len(results)} 条，已保存到 {output_file}")

