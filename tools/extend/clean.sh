#!/bin/bash

# cleanup_files.sh - 清除当前目录及子目录中的所有 .temp 和 .log 文件

# 设置要删除的文件模式
FILE_PATTERNS=("*.temp" "*.log")

# 显示开始信息
echo "正在清理文件..."
echo "查找以下类型的文件: ${FILE_PATTERNS[*]}"

# 初始化计数器
total_deleted=0

# 遍历每个文件模式
for pattern in "${FILE_PATTERNS[@]}"; do
    # 使用 find 命令查找文件
    while IFS= read -r -d $'\0' file; do
        echo "删除文件: $file"
        rm -f "$file"
        ((total_deleted++))
    done < <(find . -type f -name "$pattern" -print0)
done

# 显示统计信息
echo "清理完成。共删除 $total_deleted 个文件。"

# 安全退出
exit 0
