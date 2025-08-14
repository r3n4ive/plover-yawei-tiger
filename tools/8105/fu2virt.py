def load_fu_map(filename):
    """读取辅码到虚拟键位的映射"""
    mapping = {}
    with open(filename, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) != 2:
                continue
            ch, virt = parts
            mapping[ch] = virt
    return mapping

def convert_letters_to_virtual(input_file, fu_map_file, output_file):
    fu_map = load_fu_map(fu_map_file)

    with open(input_file, "r", encoding="utf-8") as f, \
         open(output_file, "w", encoding="utf-8") as outf:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                outf.write(line + "\n")
                continue

            code = parts[0]
            word = parts[1]
            freq = parts[2] if len(parts) > 2 else ""

            # 只转换编码中的小写字母
            new_code_chars = []
            for c in code:
                if 'a' <= c <= 'z' and c in fu_map:
                    new_code_chars.append(fu_map[c])
                else:
                    new_code_chars.append(c)
            new_code = ''.join(new_code_chars)

            # 输出转换后的行
            if freq:
                outf.write(f"{word}\t{new_code}\t{freq}\n")
            else:
                outf.write(f"{word}\t{new_code}\n")

def main():
    convert_letters_to_virtual(
        input_file="8105.converted.with_aux.txt",
        fu_map_file="fu_to_virtual_keys.txt",
        output_file="8105.converted.virtual.txt"
    )

if __name__ == "__main__":
    main()

