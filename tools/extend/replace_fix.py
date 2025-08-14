from pathlib import Path

def load_affixes(fixed_file):
    """读取 fixed.dict 返回 {type: [(word, code)]}"""
    affixes = {"prefix": [], "suffix": [], "root": []}
    with open(fixed_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) != 3:
                continue
            word, code, typ = parts
            affixes.setdefault(typ, []).append((word, code))
    return affixes


def replace_prefix(word, pinyin_list, prefix, code, log):
    """替换前缀"""
    if word.startswith(prefix):
        length = len(prefix)
        if length != len(pinyin_list[:length]):
            log.append(f"[prefix 长度不匹配] {word} | {prefix} | {pinyin_list}")
            return pinyin_list
        return [code] + pinyin_list[length:]
    return pinyin_list


def replace_suffix(word, pinyin_list, suffix, code, log):
    """替换后缀"""
    if word.endswith(suffix):
        length = len(suffix)
        if length != len(pinyin_list[-length:]):
            log.append(f"[suffix 长度不匹配] {word} | {suffix} | {pinyin_list}")
            return pinyin_list
        return pinyin_list[:-length] + [code]
    return pinyin_list


def replace_root(word, pinyin_list, root, code, log):
    """替换任意位置 root，可能多次"""
    length = len(root)
    idx = 0
    while idx <= len(word) - length:
        if word[idx:idx+length] == root:
            if length != len(pinyin_list[idx:idx+length]):
                log.append(f"[root 长度不匹配] {word} | {root} | {pinyin_list}")
                idx += 1
                continue
            pinyin_list = pinyin_list[:idx] + [code] + pinyin_list[idx+length:]
            idx += 1  # 继续向后找
        else:
            idx += 1
    return pinyin_list


def process_base_dict(base_file, affixes, output_file, log_file):
    log = []
    with open(base_file, "r", encoding="utf-8") as f, \
         open(output_file, "w", encoding="utf-8") as out:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                out.write(line + "\n")
                continue
            word, pinyin_str, freq = line.split("\t")
            pinyin_list = pinyin_str.split()

            # prefix
            for pre, code in affixes.get("prefix", []):
                pinyin_list = replace_prefix(word, pinyin_list, pre, code, log)

            # suffix
            for suf, code in affixes.get("suffix", []):
                pinyin_list = replace_suffix(word, pinyin_list, suf, code, log)

            # root
            for rt, code in affixes.get("root", []):
                pinyin_list = replace_root(word, pinyin_list, rt, code, log)

            out.write(f"{word}\t{' '.join(pinyin_list)}\t{freq}\n")

    Path(log_file).write_text("\n".join(log), encoding="utf-8")
    print(f"处理完成，结果写入 {output_file}，日志写入 {log_file}")


if __name__ == "__main__":
    affixes = load_affixes("fixed.dict")
    process_base_dict(
        "../base/base.dict.yaml",
        affixes,
        "base_with_affixes.dict",
        "replace_affix.log"
    )

