from collections import defaultdict

# 序号映射表（注意 0 表示第 10 位）
SEQ_MAP = list("DZGWIUNEAO")  # 1→D, 2→Z, ..., 9→A, 10→O

def process_file(input_file, output_file, log_file):
    # 读取数据
    code_map = defaultdict(list)  # code -> [(word, freq)]
    with open(input_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) != 3:
                continue
            word, code, freq = parts
            try:
                freq = int(freq)
            except ValueError:
                continue
            code_map[code].append((word, freq))

    out_lines = []
    log_lines = []

    # 全局唯一性检查
    used_key_owner = {}  # key -> word（第一次持有者）
    def write_with_check(key: str, word: str, freq: int):
        if key in used_key_owner and used_key_owner[key] != word:
            log_lines.append(f"CONFLICT: {key} 已用于 {used_key_owner[key]}，再次用于 {word}")
        else:
            used_key_owner.setdefault(key, word)
        out_lines.append(f"{key}\t{word}\t{freq}")

    # 遍历处理
    for code, items in code_map.items():
        items.sort(key=lambda x: (-x[1], x[0]))  # 按频降序、词典序排序
        n = len(items)

        if n == 1:
            # 规则 1: 唯一词直接用原 code
            w, f = items[0]
            write_with_check(code, w, f)

        elif n == 2:
            # 规则 2: 高频词用原 code，低频词加 /X-
            (w_hi, f_hi), (w_lo, f_lo) = items
            write_with_check(code, w_hi, f_hi)
            write_with_check(f"{code}/X-", w_lo, f_lo)

        else:
            # 规则 3: ≥3 个词
            if n > 10:
                log_lines.append(f"TOO_MANY: {code} 有 {n} 个候选，超过 10 个，不处理")
                continue

            # 总览
            overview_word = "[" + "|".join(w for w, _ in items) + "]"
            total_freq = sum(f for _, f in items)
            write_with_check(code, overview_word, total_freq)

            # 候选词依次编号
            for idx, (w, f) in enumerate(items, start=1):
                seq_char = SEQ_MAP[idx - 1]  # idx 从 1 开始
                new_code = f"{code}/XNE-{seq_char}"
                write_with_check(new_code, w, f)

            # 词频最高的单独加 /X-W
            w1, f1 = items[0]
            write_with_check(f"{code}/X-W", w1, f1)

    # 写文件
    with open(output_file, "w", encoding="utf-8") as outf:
        outf.write("\n".join(out_lines) + "\n")

    with open(log_file, "w", encoding="utf-8") as logf:
        logf.write("\n".join(log_lines) + "\n")


if __name__ == "__main__":
    process_file(
        input_file="8105.converted.virtual.txt",
        output_file="8105.reencoded.txt",
        log_file="8105.reencode.log"
    )

