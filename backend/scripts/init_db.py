#!/usr/bin/env python
"""
数据库初始化脚本

创建所有表并插入初始数据
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.database import engine, Base, init_db
from app.models import *  # 导入所有模型


# 初始话题数据
TOPICS_DATA = {
    "初一": [
        "校园生活", "家庭亲情", "兴趣爱好", "节日习俗",
        "动物自然", "梦想成长", "友谊互助", "健康饮食"
    ],
    "初二": [
        "个人成长", "科技生活", "文化交流", "环境保护",
        "运动健康", "艺术创造", "旅行探索", "社会服务"
    ],
    "初三": [
        "人生哲理", "科技伦理", "跨文化理解", "全球问题",
        "职业规划", "心理健康", "社会现象", "历史文化",
        "创新思维", "人际关系", "压力应对", "责任担当"
    ]
}


async def create_fts_table():
    """创建FTS5全文搜索虚拟表"""
    async with engine.begin() as conn:
        # 检查FTS表是否已存在
        result = await conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='reading_passage_fts'"
        ))
        if result.fetchone() is None:
            await conn.execute(text("""
                CREATE VIRTUAL TABLE reading_passage_fts USING fts5(
                    content,
                    title,
                    primary_topic,
                    content='reading_passages',
                    content_rowid='id',
                    tokenize='unicode61'
                )
            """))
            print("✓ 创建FTS5虚拟表成功")
        else:
            print("✓ FTS5虚拟表已存在")


async def insert_initial_topics():
    """插入初始话题数据"""
    from sqlalchemy import select
    from app.models.topic import Topic

    async with engine.begin() as conn:
        # 检查是否已有数据
        result = await conn.execute(text("SELECT COUNT(*) FROM topics"))
        count = result.scalar()

        if count > 0:
            print(f"✓ 话题数据已存在 ({count}条)")
            return

        # 插入话题数据
        for grade_level, topics in TOPICS_DATA.items():
            for sort_order, topic_name in enumerate(topics, 1):
                await conn.execute(text(
                    "INSERT INTO topics (name, grade_level, sort_order) VALUES (:name, :grade, :order)"
                ), {"name": topic_name, "grade": grade_level, "order": sort_order})

        print(f"✓ 插入初始话题数据成功 ({sum(len(t) for t in TOPICS_DATA.values())}条)")


async def main():
    """主函数"""
    print("=" * 50)
    print("北京中考英语教研资料系统 - 数据库初始化")
    print("=" * 50)

    # 1. 创建所有表
    print("\n[1/3] 创建数据库表...")
    await init_db()
    print("✓ 数据库表创建成功")

    # 2. 创建FTS5虚拟表
    print("\n[2/3] 创建全文搜索表...")
    await create_fts_table()

    # 3. 插入初始数据
    print("\n[3/3] 插入初始数据...")
    await insert_initial_topics()

    print("\n" + "=" * 50)
    print("数据库初始化完成!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
