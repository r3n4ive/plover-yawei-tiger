from collections import defaultdict

def load_tiger2(filename):
    tiger_map = {}
    with open(filename, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or '=' not in line:
                continue
            char, code = line.split('=', 1)
            if code:  # 只取第一个字符作为辅码
                tiger_map[char] = code[0]
    return tiger_map

def process_base_with_aux(input_file, tiger_file, output_file, log_file):
    tiger_map = load_tiger2(tiger_file)

    # 读取原始数据
    entries = []
    code_to_entries = defaultdict(list)
    with open(input_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) != 3:
                continue
            word, code, freq = parts
            freq = int(freq)
            entry = {"word": word, "code": code, "freq": freq}
            entries.append(entry)
            code_to_entries[code].append(entry)

    final_entries = []
    aux_codes = defaultdict(list)

    # 遍历每个编码组
    for code, group in code_to_entries.items():
        if len(group) == 1:
            # 非重码，保持原编码
            e = group[0]
            final_entries.append(f"{e['code']}\t{e['word']}\t{e['freq']}")
        else:
            # 重码，按词频降序排序
            group.sort(key=lambda x: x['freq'], reverse=True)
            # 最高频词保持原编码
            first = group[0]
            final_entries.append(f"{first['code']}\t{first['word']}\t{first['freq']}")
            # 其余词加辅码
            for e in group[1:]:
                f1 = tiger_map.get(e['word'][0], "")
                f2 = tiger_map.get(e['word'][-1], "")
                new_code = f"{e['code']}/{f1}-{f2}"
                final_entries.append(f"{new_code}\t{e['word']}\t{e['freq']}")
                aux_codes[new_code].append(e['word'])

    # 写最终编码表
    with open(output_file, "w", encoding="utf-8") as outf:
        for line in final_entries:
            outf.write(line + "\n")

    # 统计重码情况
    count_stat = defaultdict(int)
    for words in aux_codes.values():
        count_stat[len(words)] += 1

    # 写 log
    with open(log_file, "w", encoding="utf-8") as logf:
        logf.write("加辅码后的重码统计（只统计加辅码后的重码）:\n")
        for n in sorted(count_stat.keys(), reverse=True):
            logf.write(f"重码数 {n} 的编码有 {count_stat[n]} 个\n")
        logf.write("\n重码详情:\n")
        # 按重码数量降序输出
        sorted_aux = sorted(aux_codes.items(), key=lambda x: len(x[1]), reverse=True)
        for code, words in sorted_aux:
            logf.write(f"{code} : {' '.join(words)}\n")

if __name__ == "__main__":
    process_base_with_aux(
        input_file="root_filter2.txt.temp",
        tiger_file="../theory_map/tiger2.txt",
        output_file="root.with_aux.txt.temp",
        log_file="add_fu.log"
    )

