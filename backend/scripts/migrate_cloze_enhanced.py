#!/usr/bin/env python
"""
迁移完形填空增强功能

新增内容：
1. 创建 textbook_vocab 表（课本单词表）
2. 为 cloze_points 表添加新字段（固定搭配、词义辨析、熟词僻义专用字段）
"""
import sqlite3
import sys
from pathlib import Path

# 数据库路径
DB_PATH = Path(__file__).parent.parent / "database" / "teaching.db"


def check_column_exists(cursor, table_name, column_name):
    """检查列是否存在"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns


def check_table_exists(cursor, table_name):
    """检查表是否存在"""
    cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
    return cursor.fetchone() is not None


def migrate():
    """迁移数据库"""
    print("=" * 60)
    print("完形填空增强功能迁移")
    print("=" * 60)

    if not DB_PATH.exists():
        print(f"✗ 数据库文件不存在: {DB_PATH}")
        print("  数据库将在应用启动时自动创建，无需手动迁移")
        return True

    # 备份数据库
    backup_path = DB_PATH.parent / f"{DB_PATH.name}.backup_enhanced"
    import shutil
    shutil.copy(DB_PATH, backup_path)
    print(f"✓ 备份数据库到: {backup_path}\n")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # ============================================================================
        #  1. 创建 textbook_vocab 表（如果不存在）
        # ============================================================================
        print("1. 检查 textbook_vocab 表...")

        if not check_table_exists(cursor, "textbook_vocab"):
            print("   创建 textbook_vocab 表...")
            create_textbook_vocab_sql = """
            CREATE TABLE textbook_vocab (
                id INTEGER NOT NULL PRIMARY KEY,
                word VARCHAR(255) NOT NULL,
                pos VARCHAR(100),
                definition TEXT NOT NULL,
                publisher VARCHAR(50) NOT NULL,
                grade VARCHAR(20) NOT NULL,
                semester VARCHAR(10) NOT NULL,
                unit VARCHAR(50),
                created_at DATETIME
            )
            """
            cursor.execute(create_textbook_vocab_sql)

            # 创建索引
            cursor.execute("CREATE INDEX idx_textbook_vocab_word ON textbook_vocab(word)")
            cursor.execute("CREATE INDEX idx_textbook_vocab_publisher_grade ON textbook_vocab(publisher, grade)")
            print("   ✓ textbook_vocab 表已创建")
        else:
            print("   ✓ textbook_vocab 表已存在，跳过")

        # ============================================================================
        #  2. 为 cloze_points 表添加新字段
        # ============================================================================
        print("\n2. 检查 cloze_points 表新字段...")

        new_columns = [
            # 固定搭配专用
            ("phrase", "VARCHAR(255)"),
            ("similar_phrases", "TEXT"),
            # 词义辨析专用
            ("word_analysis", "TEXT"),
            ("dictionary_source", "VARCHAR(100)"),
            # 熟词僻义专用
            ("textbook_meaning", "TEXT"),
            ("textbook_source", "VARCHAR(100)"),
            ("context_meaning", "TEXT"),
            ("similar_words", "TEXT"),
            # 通用
            ("tips", "TEXT"),
            # 人工校对
            ("point_verified", "BOOLEAN DEFAULT 0"),
        ]

        added_count = 0
        for column_name, column_type in new_columns:
            if not check_column_exists(cursor, "cloze_points", column_name):
                cursor.execute(f"ALTER TABLE cloze_points ADD COLUMN {column_name} {column_type}")
                print(f"   ✓ 添加列: {column_name}")
                added_count += 1
            else:
                print(f"   - 列已存在: {column_name}")

        if added_count == 0:
            print("   所有新字段已存在，无需添加")

        # ============================================================================
        #  3. 提交更改
        # ============================================================================
        conn.commit()

        print("\n" + "=" * 60)
        print("迁移完成!")
        print("=" * 60)
        print("\n新增内容：")
        print("  • textbook_vocab 表（课本单词表）")
        print("  • cloze_points 新增字段：")
        print("    - 固定搭配: phrase, similar_phrases")
        print("    - 词义辨析: word_analysis, dictionary_source")
        print("    - 熟词僻义: textbook_meaning, textbook_source, context_meaning, similar_words")
        print("    - 通用: tips, point_verified")

        return True

    except Exception as e:
        print(f"\n✗ 迁移失败: {e}")
        print("正在恢复备份...")
        conn.close()
        shutil.copy(backup_path, DB_PATH)
        print(f"✓ 已从备份恢复: {backup_path}")
        return False

    finally:
        conn.close()


if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)
