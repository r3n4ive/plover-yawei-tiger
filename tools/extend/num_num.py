from itertools import product

input_file = "num.dict"  # 你的文件名
output_file = "num_num.dict"

# 读取字和编码
char_code_map = {}
with open(input_file, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        char, code = parts[0], parts[1]
        char_code_map[char] = code

chars = list(char_code_map.keys())

with open(output_file, "w", encoding="utf-8") as f_out:
    for c1, c2 in product(chars, repeat=2):
        code1 = char_code_map[c1]
        code2 = char_code_map[c2]
        combined_word = c1 + c2
        combined_code = f"{code1}-{code2}"
        f_out.write(f"{combined_word}\t{combined_code}\n")

print(f"生成完成，共 {len(chars)**2} 条组合，保存到 {output_file}")

