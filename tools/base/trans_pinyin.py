import os
from collections import defaultdict

def load_tedingzi(filename):
    mapping = {}
    with open(filename, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "\t" not in line:
                continue
            char, code = line.split("\t", 1)
            mapping[char] = code
    return mapping

def load_pinyin_map(filename):
    mapping = defaultdict(list)
    reverse_map = defaultdict(set)
    with open(filename, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "\t" not in line:
                continue
            py, code = line.split("\t", 1)
            mapping[py].append(code)
            reverse_map[code].add(py)
    return mapping, reverse_map

def interleaved_join(codes):
    if not codes:
        return ""
    result = codes[0]
    for idx, code in enumerate(codes[1:], 1):
        sep = "-" if idx % 2 == 1 else "/"
        result += sep + code
    return result

def expand_codes(pinyin_list, pinyin_map):
    """
    输入：['ting', 'le']
    输出：所有可能的编码组合
    """
    from itertools import product
    code_options = []
    for py in pinyin_list:
        if py in pinyin_map:
            code_options.append(pinyin_map[py])
        else:
            return []  # 缺少映射
    # 笛卡尔积生成所有组合
    return list(product(*code_options))

def process_word_table(base_file, tedingzi_map, pinyin_map, reverse_map, output_file, log_file):
    bad_lines = []
    converted_lines = []
    line_no = 0

    with open(base_file, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) != 3:
                bad_lines.append(f"格式错误: {line_no}: {line}")
                continue

            word, pinyin_str, freq = parts
            chars = list(word)
            pinyins = pinyin_str.split()

            if len(chars) != len(pinyins):
                bad_lines.append(f"字数与音节数不匹配: {line_no}: {line}")
                continue

            # 检查是否有特定字映射
            replaced_pinyins = []
            for ch, py in zip(chars, pinyins):
                if ch in tedingzi_map:
                    replaced_pinyins.append(tedingzi_map[ch])
                else:
                    replaced_pinyins.append(py)

            # 展开所有编码组合
            all_code_combos = expand_codes(replaced_pinyins, pinyin_map)
            if not all_code_combos:
                bad_lines.append(f"缺少拼音映射: {line_no}: {line}")
                continue

            # 记录一对多情况
            for py in set(replaced_pinyins):
                if py in pinyin_map and len(pinyin_map[py]) > 1:
                    bad_lines.append(f"[一对多] {py} → {pinyin_map[py]} (行 {line_no})")

            # 记录多对一情况
            seen_codes = set()
            for py in set(replaced_pinyins):
                if py in pinyin_map:
                    for code in pinyin_map[py]:
                        if len(reverse_map[code]) > 1:
                            bad_lines.append(f"[多对一] {code} ← {list(reverse_map[code])} (行 {line_no})")

            # 生成所有组合行
            for combo in all_code_combos:
                code = interleaved_join(combo)
                converted_lines.append(f"{word}\t{code}\t{freq}")

    # 写输出文件
    with open(output_file, "w", encoding="utf-8") as outf:
        for line in converted_lines:
            outf.write(line + "\n")

    # 写 log 文件
    with open(log_file, "w", encoding="utf-8") as lf:
        lf.write("处理异常/记录行:\n")
        for bl in bad_lines:
            lf.write(bl + "\n")
        lf.write(f"\n总行数: {line_no}\n")
        lf.write(f"成功转换行数: {len(converted_lines)}\n")
        lf.write(f"记录的异常/特殊情况行数: {len(bad_lines)}\n")

def main():
    tedingzi_map = {}  # 如果需要加载特定字就用 load_tedingzi
    pinyin_map, reverse_map = load_pinyin_map("../theory_map/pinyin_to_virtual_keys.txt")

    process_word_table(
        base_file="base.dict.yaml",
        tedingzi_map=tedingzi_map,
        pinyin_map=pinyin_map,
        reverse_map=reverse_map,
        output_file="base.converted.txt.temp",
        log_file="trans_pinyin.log"
    )

if __name__ == "__main__":
    main()

