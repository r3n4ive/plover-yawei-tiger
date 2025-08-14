from collections import defaultdict

def load_pinyin_map(filename):
    """读取拼音到虚拟键位的映射"""
    mapping = {}
    with open(filename, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) != 2:
                continue
            py, code = parts
            mapping[py] = code
    return mapping

def process_8105(input_file, pinyin_map_file, output_file, lack_file, log_file):
    pinyin_map = load_pinyin_map(pinyin_map_file)
    lack_yin = set()
    final_entries = []
    errors = []

    with open(input_file, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) != 3:
                errors.append(f"格式错误 (行 {lineno}): {line}")
                continue

            char, yin, freq = parts
            if not yin:
                errors.append(f"缺少拼音 (行 {lineno}): {line}")
                continue

            try:
                freq = int(freq)
            except ValueError:
                errors.append(f"词频非数字 (行 {lineno}): {line}")
                continue

            # 转换拼音到虚拟键位
            if yin in pinyin_map:
                code = pinyin_map[yin]
                final_entries.append(f"{char}\t{code}\t{freq}")
            else:
                lack_yin.add(yin)
                errors.append(f"缺少拼音映射 (行 {lineno}): {line}")

    # 写转换后的码表
    with open(output_file, "w", encoding="utf-8") as outf:
        for entry in final_entries:
            outf.write(entry + "\n")

    # 写缺失拼音文件
    with open(lack_file, "w", encoding="utf-8") as lf:
        for py in sorted(lack_yin):
            lf.write(py + "\n")

    # 写日志
    with open(log_file, "w", encoding="utf-8") as logf:
        logf.write("8105.dict.yaml 转换日志\n")
        logf.write(f"总转换条目: {len(final_entries)}\n")
        logf.write(f"缺少拼音映射条目: {len(lack_yin)}\n\n")
        if errors:
            logf.write("错误/警告详情:\n")
            for err in errors:
                logf.write(err + "\n")

if __name__ == "__main__":
    process_8105(
        input_file="8105.dict.yaml",
        pinyin_map_file="pinyin_to_virtual_keys.txt",
        output_file="8105.converted.txt",
        lack_file="lack_yin.txt",
        log_file="trans_pinyin.log"
    )

