# find_affixes.py
from pathlib import Path

fixed_path = Path("fixed.dict")
base_path = Path("../base/base.dict.yaml")
log_path = Path("analysis.log")

# 读取 fixed.dict 的第一列（词缀本身）
affixes = []
with open(fixed_path, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 1:
            affix = parts[0]
            if len(affix) > 1:
                affixes.append(affix)

# 去重（有些 root / prefix / suffix 可能重复）
affixes = sorted(set(affixes))

# 扫描 base.dict.yaml，找出包含任一词缀的词语
matches = []
with open(base_path, "r", encoding="utf-8") as f:
    for line in f:
        line = line.rstrip("\n")
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        word = parts[0]
        for affix in affixes:
            if affix in word:
                matches.append(line)
                break  # 一个词缀命中即可，不重复记录

# 写 log
with open(log_path, "w", encoding="utf-8") as f:
    for m in matches:
        f.write(m + "\n")

print(f"共找到 {len(matches)} 条记录，已保存到 {log_path}")

