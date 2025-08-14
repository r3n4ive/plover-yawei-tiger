# 文件路径
num_file = "num_num.dict"
input_file = "root_filter.txt.temp"
output_file = "root_filter2.txt.temp"
log_file = "root_filter2.log"

# 读取 num_num.dict 中的词
num_words = set()
with open(num_file, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        word = line.split()[0]
        num_words.add(word)

filtered_lines = []
removed_lines = []

# 读取 root_filter.txt.temp 并过滤
with open(input_file, "r", encoding="utf-8") as f:
    for line in f:
        line_strip = line.strip()
        if not line_strip:
            continue
        word = line_strip.split("\t")[0]
        if word in num_words:
            removed_lines.append(line_strip)
        else:
            filtered_lines.append(line_strip)

# 写入过滤后的文件
with open(output_file, "w", encoding="utf-8") as f:
    for line in filtered_lines:
        f.write(line + "\n")

# 写入 log 文件
with open(log_file, "w", encoding="utf-8") as f:
    f.write("被过滤掉的词:\n")
    for line in removed_lines:
        f.write(line + "\n")

print(f"过滤完成：{len(filtered_lines)} 条保留，{len(removed_lines)} 条被移除。")

