"""
作文分类树全量迁移脚本

用途：
1. 确保 writing_categories 表与新字段存在
2. 将旧作文全量重分到数据库分类树
3. 重建按子类绑定的模板，并把既有范文重新挂到新模板

用法：
    cd backend
    . .venv/bin/activate
    python scripts/migrate_writing_categories.py
"""
from __future__ import annotations

import asyncio
import argparse
from pathlib import Path

from sqlalchemy import delete, select, update

ROOT = Path(__file__).resolve().parents[1]
import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import models  # noqa: F401  # 确保模型注册
from app.database import async_session_factory, init_db
from app.models.writing import WritingSample, WritingTask, WritingTemplate
from app.services.writing_service import WritingService


async def migrate(limit: int | None = None, batch_size: int = 25) -> None:
    await init_db()

    async with async_session_factory() as session:
        service = WritingService(session)

        print("1/4 清理旧模板引用与旧一级分类字段...")
        await session.execute(update(WritingSample).values(template_id=None))
        await session.execute(delete(WritingTemplate))
        await session.execute(
            update(WritingTask).values(
                writing_type=None,
                application_type=None,
                primary_topic=None,
                topic_verified=False,
            )
        )
        await session.commit()

        print("2/4 全量重分类作文...")
        summary = await service.reclassify_all_tasks(limit=limit, batch_size=batch_size)
        print(f"   已分类 {summary['classified']} 条，失败 {summary['failed']} 条")

        print("3/4 重建子类模板并回挂范文...")
        updated_samples = await service.reset_templates_for_categories()
        print(f"   已回挂 {updated_samples} 条范文模板引用")

        print("4/4 检查未分类残留...")
        remaining = await session.execute(
            select(WritingTask).where(WritingTask.category_id.is_(None))
        )
        remaining_count = len(list(remaining.scalars().all()))
        print(f"迁移完成，仍未分类作文数：{remaining_count}")


def main() -> None:
    parser = argparse.ArgumentParser(description="全量迁移作文分类树")
    parser.add_argument("--limit", type=int, default=None, help="只迁移前 N 条作文，便于验证")
    parser.add_argument("--batch-size", type=int, default=25, help="分批提交大小")
    args = parser.parse_args()
    asyncio.run(migrate(limit=args.limit, batch_size=args.batch_size))


if __name__ == "__main__":
    main()
