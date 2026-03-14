#!/usr/bin/env python
"""
迁移完形填空考点表结构

只修改约束，保留所有现有数据
"""
import sqlite3
import sys
from pathlib import Path

# 数据库路径
DB_PATH = Path(__file__).parent.parent / "database" / "teaching.db"


def migrate():
    """迁移数据库"""
    print("=" * 60)
    print("完形填空考点表迁移")
    print("=" * 60)

    if not DB_PATH.exists():
        print(f"✗ 数据库文件不存在: {DB_PATH}")
        return False

    # 备份数据库
    backup_path = DB_PATH.parent / f"{DB_PATH.name}.backup"
    import shutil
    shutil.copy(DB_PATH, backup_path)
    print(f"✓ 备份数据库到: {backup_path}\n")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # 1. 读取现有数据
        print("1. 读取现有数据...")
        cursor.execute("SELECT * FROM cloze_points")
        rows = cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        print(f"   读取了 {len(rows)} 条记录\n")

        # 2. 获取创建索引和外键的SQL
        print("2. 备份索引...")
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='cloze_points'")
        indexes = cursor.fetchall()
        print(f"   找到 {len(indexes)} 个索引\n")

        # 3. 删除旧表
        print("3. 删除旧表...")
        cursor.execute("DROP TABLE IF EXISTS cloze_points_new")
        cursor.execute("DROP TABLE IF EXISTS cloze_points")
        print("   ✓ 旧表已删除\n")

        # 4. 创建新表（新的约束）
        print("4. 创建新表（只包含3种考点类型）...")
        create_sql = """
        CREATE TABLE cloze_points (
            id INTEGER NOT NULL,
            cloze_id INTEGER NOT NULL,
            blank_number INTEGER,
            correct_answer VARCHAR(100),
            correct_word VARCHAR(255),
            options TEXT,
            point_type VARCHAR(50),
            point_detail TEXT,
            translation TEXT,
            explanation TEXT,
            confusion_words TEXT,
            sentence TEXT,
            char_position INTEGER,
            created_at DATETIME,
            PRIMARY KEY (id),
            CONSTRAINT ck_point_type CHECK (point_type IN ('固定搭配', '词义辨析', '熟词僻义')),
            FOREIGN KEY(cloze_id) REFERENCES cloze_passages (id)
        )
        """
        cursor.execute(create_sql)
        print("   ✓ 新表已创建\n")

        # 5. 恢复数据
        print("5. 恢复数据...")
        placeholders = ', '.join(['?'] * len(columns))
        insert_sql = f"INSERT INTO cloze_points ({', '.join(columns)}) VALUES ({placeholders})"
        cursor.executemany(insert_sql, rows)
        print(f"   ✓ 恢复了 {len(rows)} 条记录\n")

        # 6. 提交更改
        conn.commit()
        print("6. 迁移完成!")
        print("=" * 60)

        # 验证
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='cloze_points'")
        new_table_sql = cursor.fetchone()[0]

        if "'固定搭配', '词义辨析', '熟词僻义'" in new_table_sql:
            print("✓ 验证通过：新约束已生效")
            print("✓ 只包含3种考点类型：固定搭配、词义辨析、熟词僻义")
            return True
        else:
            print("✗ 验证失败：约束未正确更新")
            return False

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
