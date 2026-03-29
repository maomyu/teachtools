"""
按新子类 Prompt 全量重建作文模板。

用途：
1. 找出所有已有作文题的子类
2. 基于同子类真题示例，强制刷新该子类模板
3. 让讲义/详情页读取到稳定的新模板，而不是在只读接口里临时修模板

用法：
    cd backend
    . .venv/bin/activate
    python scripts/rebuild_writing_templates.py
    python scripts/rebuild_writing_templates.py --limit 10
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

ROOT = Path(__file__).resolve().parents[1]
import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import models  # noqa: F401  # 确保模型注册
from app.database import async_session_factory, init_db
from app.models.writing import WritingTask
from app.services.writing_service import WritingService


async def rebuild(limit: int | None = None) -> None:
    await init_db()

    async with async_session_factory() as session:
        result = await session.execute(
            select(WritingTask.category_id, func.max(WritingTask.id).label("anchor_task_id"))
            .where(WritingTask.category_id.isnot(None))
            .group_by(WritingTask.category_id)
            .order_by(WritingTask.category_id)
        )
        rows = list(result.all())

    if limit is not None:
        rows = rows[:limit]

    print(f"开始重建作文模板，共 {len(rows)} 个子类...")

    success = 0
    failed = 0

    for index, row in enumerate(rows, start=1):
        async with async_session_factory() as session:
            service = WritingService(session)
            try:
                anchor_result = await session.execute(
                    select(WritingTask)
                    .options(
                        selectinload(WritingTask.paper),
                        selectinload(WritingTask.category),
                        selectinload(WritingTask.major_category),
                        selectinload(WritingTask.group_category),
                    )
                    .where(WritingTask.id == row.anchor_task_id)
                )
                anchor_task = anchor_result.scalar_one()
                template = await service.get_or_create_template(
                    row.category_id,
                    anchor_task=anchor_task,
                    force_refresh=True,
                )
                success += 1
                print(
                    f"[{index}/{len(rows)}] 子类={anchor_task.category.path} -> "
                    f"template_id={template.id}"
                )
            except Exception as exc:
                failed += 1
                print(f"[{index}/{len(rows)}] category_id={row.category_id} 失败: {exc}")

    print("模板重建完成")
    print(f"成功 {success} 个，失败 {failed} 个")


def main() -> None:
    parser = argparse.ArgumentParser(description="按新子类 Prompt 全量重建作文模板")
    parser.add_argument("--limit", type=int, default=None, help="只重建前 N 个子类，便于验证")
    args = parser.parse_args()
    asyncio.run(rebuild(limit=args.limit))


if __name__ == "__main__":
    main()
