#!/usr/bin/env python
"""
完形填空考点分类系统迁移脚本

功能:
1. 添加新字段到 cloze_points 表 (primary_point_code, legacy_point_type)
2. 将旧 point_type 映射到新 primary_point_code
3. 创建新关联表 (point_type_definitions, cloze_secondary_points, cloze_rejection_points)
4. 插入 16 个考点定义数据

使用方法:
    cd backend
    python scripts/migrate_point_types.py

注意: 运行前请先备份数据库！
"""
import sqlite3
import json
from pathlib import Path
from datetime import datetime

# 数据库路径
DB_PATH = Path(__file__).parent.parent / "database" / "teaching.db"

# 旧类型到新类型的映射
LEGACY_TYPE_MAPPING = {
    "固定搭配": "C2",  # -> 句法语法类-固定搭配
    "词义辨析": "D1",  # -> 词汇选项类-常规词义辨析
    "熟词僻义": "D2",  # -> 词汇选项类-熟词僻义
}

# 16 个考点定义
POINT_TYPE_DEFINITIONS = [
    # A. 语篇理解类 (P1)
    {"code": "A1", "category": "A", "category_name": "语篇理解类", "name": "上下文语义推断", "priority": 1,
     "description": "根据空前空后及前后句推断空格应表达的大致语义"},
    {"code": "A2", "category": "A", "category_name": "语篇理解类", "name": "复现与照应", "priority": 1,
     "description": "前文或后文出现与答案意思相同、相近、相反或同一主题链上的词"},
    {"code": "A3", "category": "A", "category_name": "语篇理解类", "name": "代词指代", "priority": 1,
     "description": "通过代词回指确定人物、事物或信息对象"},
    {"code": "A4", "category": "A", "category_name": "语篇理解类", "name": "情节/行为顺序", "priority": 1,
     "description": "根据故事发展顺序、动作先后顺序判断哪个词最合理"},
    {"code": "A5", "category": "A", "category_name": "语篇理解类", "name": "情感态度", "priority": 1,
     "description": "根据人物心情、作者评价、语境色彩判断褒贬方向"},

    # B. 逻辑关系类 (P1)
    {"code": "B1", "category": "B", "category_name": "逻辑关系类", "name": "并列一致", "priority": 1,
     "description": "前后内容语义一致、方向一致、性质相近"},
    {"code": "B2", "category": "B", "category_name": "逻辑关系类", "name": "转折对比", "priority": 1,
     "description": "前后语义相反或预期相反"},
    {"code": "B3", "category": "B", "category_name": "逻辑关系类", "name": "因果关系", "priority": 1,
     "description": "前因后果或前果后因"},
    {"code": "B4", "category": "B", "category_name": "逻辑关系类", "name": "其他逻辑关系", "priority": 1,
     "description": "递进、让步、条件、举例、总结等关系"},

    # C. 句法语法类 (P2)
    {"code": "C1", "category": "C", "category_name": "句法语法类", "name": "词性与句子成分", "priority": 2,
     "description": "根据句法位置判断所需词类"},
    {"code": "C2", "category": "C", "category_name": "句法语法类", "name": "固定搭配", "priority": 2,
     "description": "某些词必须和特定介词、名词、动词或句型一起使用"},
    {"code": "C3", "category": "C", "category_name": "句法语法类", "name": "语法形式限制", "priority": 2,
     "description": "由时态、语态、主谓一致、非谓语等形式规则限制"},

    # D. 词汇选项类 (P3)
    {"code": "D1", "category": "D", "category_name": "词汇选项类", "name": "常规词义辨析", "priority": 3,
     "description": "几个选项词性相同、意思相近，需要根据语境精细区分"},
    {"code": "D2", "category": "D", "category_name": "词汇选项类", "name": "熟词僻义", "priority": 3,
     "description": "常见词在特定语境中使用非常见义项"},

    # E. 常识主题类 (P3)
    {"code": "E1", "category": "E", "category_name": "常识主题类", "name": "生活常识/场景常识", "priority": 3,
     "description": "根据现实世界常识判断哪个选项合理"},
    {"code": "E2", "category": "E", "category_name": "常识主题类", "name": "主题主旨与人物共情", "priority": 3,
     "description": "从全文主题和人物心理出发理解作者真正想表达的意思"},
]


def backup_database(db_path: Path) -> Path:
    """备份数据库"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.parent / f"teaching_backup_{timestamp}.db"

    import shutil
    shutil.copy2(db_path, backup_path)
    print(f"✓ 数据库已备份到: {backup_path}")
    return backup_path


def check_column_exists(cursor: sqlite3.Cursor, table: str, column: str) -> bool:
    """检查列是否存在"""
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns


def check_table_exists(cursor: sqlite3.Cursor, table: str) -> bool:
    """检查表是否存在"""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cursor.fetchone() is not None


def migrate():
    """执行迁移"""
    print("=" * 60)
    print("完形填空考点分类系统迁移脚本")
    print("=" * 60)

    if not DB_PATH.exists():
        print(f"✗ 数据库文件不存在: {DB_PATH}")
        return

    # 备份数据库
    backup_database(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # ===== Phase 1: 添加新字段 =====
        print("\n[Phase 1] 添加新字段到 cloze_points 表...")

        if not check_column_exists(cursor, "cloze_points", "primary_point_code"):
            cursor.execute("ALTER TABLE cloze_points ADD COLUMN primary_point_code VARCHAR(20)")
            print("  ✓ 添加 primary_point_code 字段")
        else:
            print("  - primary_point_code 字段已存在，跳过")

        if not check_column_exists(cursor, "cloze_points", "legacy_point_type"):
            cursor.execute("ALTER TABLE cloze_points ADD COLUMN legacy_point_type VARCHAR(50)")
            print("  ✓ 添加 legacy_point_type 字段")
        else:
            print("  - legacy_point_type 字段已存在，跳过")

        # ===== Phase 2: 数据映射 =====
        print("\n[Phase 2] 映射旧类型到新类型...")

        cursor.execute("SELECT id, point_type FROM cloze_points WHERE point_type IS NOT NULL")
        rows = cursor.fetchall()

        updated_count = 0
        for row in rows:
            point_id, old_type = row
            new_code = LEGACY_TYPE_MAPPING.get(old_type)
            if new_code:
                cursor.execute(
                    "UPDATE cloze_points SET primary_point_code = ?, legacy_point_type = ? WHERE id = ?",
                    (new_code, old_type, point_id)
                )
                updated_count += 1

        print(f"  ✓ 已更新 {updated_count} 条记录")

        # ===== Phase 3: 创建新表 =====
        print("\n[Phase 3] 创建新关联表...")

        # 考点定义表
        if not check_table_exists(cursor, "point_type_definitions"):
            cursor.execute("""
                CREATE TABLE point_type_definitions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code VARCHAR(20) UNIQUE NOT NULL,
                    category VARCHAR(10) NOT NULL,
                    category_name VARCHAR(50) NOT NULL,
                    name VARCHAR(50) NOT NULL,
                    priority INTEGER NOT NULL,
                    description TEXT
                )
            """)
            print("  ✓ 创建 point_type_definitions 表")
        else:
            print("  - point_type_definitions 表已存在，跳过")

        # 辅助考点表
        if not check_table_exists(cursor, "cloze_secondary_points"):
            cursor.execute("""
                CREATE TABLE cloze_secondary_points (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cloze_point_id INTEGER NOT NULL,
                    point_code VARCHAR(20) NOT NULL,
                    explanation TEXT,
                    sort_order INTEGER DEFAULT 0,
                    FOREIGN KEY(cloze_point_id) REFERENCES cloze_points(id) ON DELETE CASCADE
                )
            """)
            print("  ✓ 创建 cloze_secondary_points 表")
        else:
            print("  - cloze_secondary_points 表已存在，跳过")

        # 排错点表
        if not check_table_exists(cursor, "cloze_rejection_points"):
            cursor.execute("""
                CREATE TABLE cloze_rejection_points (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cloze_point_id INTEGER NOT NULL,
                    option_word VARCHAR(255) NOT NULL,
                    point_code VARCHAR(20) NOT NULL,
                    explanation TEXT,
                    FOREIGN KEY(cloze_point_id) REFERENCES cloze_points(id) ON DELETE CASCADE
                )
            """)
            print("  ✓ 创建 cloze_rejection_points 表")
        else:
            print("  - cloze_rejection_points 表已存在，跳过")

        # ===== Phase 4: 插入考点定义 =====
        print("\n[Phase 4] 插入 16 个考点定义...")

        inserted_count = 0
        for pt in POINT_TYPE_DEFINITIONS:
            try:
                cursor.execute("""
                    INSERT INTO point_type_definitions
                    (code, category, category_name, name, priority, description)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (pt['code'], pt['category'], pt['category_name'], pt['name'], pt['priority'], pt['description']))
                inserted_count += 1
            except sqlite3.IntegrityError:
                # 已存在则跳过
                pass

        print(f"  ✓ 插入 {inserted_count} 条新定义（已存在的跳过）")

        # ===== Phase 5: 移除 CHECK 约束 =====
        print("\n[Phase 5] 移除旧的 CHECK 约束...")
        print("  ! SQLite 不支持直接移除约束，需要重建表")
        print("  ! 由于新字段已添加，旧约束不会影响新数据")
        print("  ! 如需完全移除约束，请在方便时手动执行表重建")

        # 提交事务
        conn.commit()

        print("\n" + "=" * 60)
        print("迁移完成！")
        print("=" * 60)
        print("\n统计信息:")
        print(f"  - 已更新的考点记录: {updated_count}")
        print(f"  - 新插入的考点定义: {inserted_count}")
        print(f"  - 考点定义总数: {len(POINT_TYPE_DEFINITIONS)}")

        # 验证
        print("\n验证结果:")
        cursor.execute("SELECT COUNT(*) FROM cloze_points WHERE primary_point_code IS NOT NULL")
        mapped_count = cursor.fetchone()[0]
        print(f"  - 已映射到新类型的考点: {mapped_count}")

        cursor.execute("SELECT COUNT(*) FROM point_type_definitions")
        def_count = cursor.fetchone()[0]
        print(f"  - 考点定义表记录数: {def_count}")

    except Exception as e:
        conn.rollback()
        print(f"\n✗ 迁移失败: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
