#!/usr/bin/env python3
"""
将数据库中已有的完形填空空格格式统一为 (数字)

用法：python3 backend/scripts/normalize_cloze_format.py
"""
import sqlite3
import re
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 带圈数字映射
CIRCLED_NUMBERS = {
    '①': 1, '②': 2, '③': 3, '④': 4, '⑤': 5,
    '⑥': 6, '⑦': 7, '⑧': 8, '⑨': 9, '⑩': 10,
    '⑪': 11, '⑫': 12, '⑬': 13, '⑭': 14, '⑮': 15,
    '⑯': 16, '⑰': 17, '⑱': 18, '⑲': 19, '⑳': 20,
}

# 已知的空格格式正则
BLANK_PATTERNS = [
    (r'_{2,}(\d+)_{2,}', r'(\1)'),   # ____13____ → (13)
    (r'（(\d+)）', r'(\1)'),          # （1）中文括号 → (1)
    (r'\[(\d+)\]', r'(\1)'),          # [1] 方括号 → (1)
]


def normalize_content(content: str) -> str:
    """标准化空格格式"""
    if not content:
        return content

    result = content

    # 处理带圈数字
    for char, num in CIRCLED_NUMBERS.items():
        if char in result:
            result = result.replace(char, f'({num})')

    # 处理其他正则格式
    for pattern, replacement in BLANK_PATTERNS:
        result = re.sub(pattern, replacement, result)

    return result


def main():
    """迁移数据库中的完形填空格式"""
    print("=" * 50)
    print("完形填空空格格式迁移脚本")
    print("=" * 50)

    # 连接数据库
    db_path = Path(__file__).parent.parent / "database" / "teaching.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 获取所有完形文章
    cursor.execute("SELECT id, content FROM cloze_passages")
    passages = cursor.fetchall()

    print(f"\n找到 {len(passages)} 篇完形文章")

    updated_count = 0
    for passage_id, content in passages:
        if not content:
            continue

        original = content
        normalized = normalize_content(original)

        if original != normalized:
            cursor.execute(
                "UPDATE cloze_passages SET content = ? WHERE id = ?",
                (normalized, passage_id)
            )
            updated_count += 1
            print(f"  ID={passage_id}: 已更新")
            # 显示变化
            print(f"    原始片段: {original[:100]}...")
            print(f"    标准化后: {normalized[:100]}...")
        else:
            print(f"  ID={passage_id}: 无需更新")

    conn.commit()
    conn.close()

    print(f"\n完成！共更新 {updated_count} 条记录")


if __name__ == "__main__":
    main()
