from collections import defaultdict

def load_tiger2(filename):
    tiger_map = {}
    with open(filename, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or '=' not in line:
                continue
            char, code = line.split('=', 1)
            tiger_map[char] = code  # 保留完整两位辅码
    return tiger_map

def load_tedingzi(filename):
    skip_set = set()
    with open(filename, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) != 2:
                continue
            skip_set.add(parts[0])
    return skip_set

def process_with_aux(input_file, tiger_file, tedingzi_file, output_file, log_file):
    tiger_map = load_tiger2(tiger_file)
    skip_set = load_tedingzi(tedingzi_file)

    code_groups = defaultdict(list)
    entries = []

    lack_aux_log = []

    # 读取原始码表
    with open(input_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) != 3:
                continue
            word, code, freq = parts
            if word in skip_set:
                continue  # 跳过tedingzi中的字
            freq = int(freq)
            entry = {"word": word, "code": code, "freq": freq}
            entries.append(entry)
            code_groups[code].append(entry)

    final_entries = []
    one_aux_count = 0
    two_aux_count = 0
    aux_codes = defaultdict(list)
    used_codes = set()

    for code, group in code_groups.items():
        # 按字频降序
        group_sorted = sorted(group, key=lambda x: x["freq"], reverse=True)

        for e in group_sorted:
            word = e["word"]
            fcode = tiger_map.get(word, "")
            if not fcode:
                lack_aux_log.append(word)
                continue  # 没有辅码就跳过
            # 尝试一位辅码
            one_code = f"{code}-{fcode[0]}"
            if one_code not in used_codes:
                new_code = one_code
                one_aux_count += 1
            else:
                # 使用两位辅码
                if len(fcode) >= 2:
                    new_code = f"{code}-{fcode[0]}/{fcode[1]}"
                else:
                    new_code = f"{code}-{fcode[0]}/"  # 只有一位
                two_aux_count += 1

            final_entries.append(f"{new_code}\t{word}\t{e['freq']}")
            used_codes.add(new_code)
            aux_codes[new_code].append(word)

    # 写输出文件
    with open(output_file, "w", encoding="utf-8") as outf:
        for line in final_entries:
            outf.write(line + "\n")

    # 写日志
    with open(log_file, "w", encoding="utf-8") as logf:
        logf.write(f"使用一位辅码数量: {one_aux_count}\n")
        logf.write(f"使用两位辅码数量: {two_aux_count}\n\n")
        if lack_aux_log:
            logf.write("缺少辅码的字（未生成编码）:\n")
            logf.write("\n".join(lack_aux_log) + "\n\n")

        # 统计重码情况
        count_stat = defaultdict(int)
        for words in aux_codes.values():
            if len(words) > 1:
                count_stat[len(words)] += 1

        logf.write("加辅码后的重码统计:\n")
        for n in sorted(count_stat.keys(), reverse=True):
            logf.write(f"重码数 {n} 的编码有 {count_stat[n]} 个\n")
        logf.write("\n重码详情（按重码数降序）:\n")
        sorted_aux = sorted(aux_codes.items(), key=lambda x: len(x[1]), reverse=True)
        for code, words in sorted_aux:
            if len(words) > 1:
                logf.write(f"{code} : {' '.join(words)}\n")

if __name__ == "__main__":
    process_with_aux(
        input_file="8105.converted.txt",
        tiger_file="tiger2.txt",
        tedingzi_file="tedingzi.txt",
        output_file="8105.converted.with_aux.txt",
        log_file="add_fu.log"
    )

