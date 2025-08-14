import json
from collections import defaultdict

def txt_to_json(input_file, output_file):
    code_map = defaultdict(list)

    with open(input_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if '\t' not in line:
                continue
            code, char, freq = line.split("\t")
            code = code.strip()
            char = char.strip()
            code_map[code].append(char)

    # 将只含一个字的编码直接存为字符串
    final_map = {}
    for code, chars in code_map.items():
        if len(chars) == 1:
            final_map[code] = chars[0]
        else:
            final_map[code] = chars

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(final_map, f, ensure_ascii=False, indent=2)

def main():
    txt_to_json("8105.reencoded.txt", "8105.json")

if __name__ == "__main__":
    main()

