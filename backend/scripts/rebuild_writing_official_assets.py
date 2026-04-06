"""
按“一个子类一套模板、一题一篇正式范文”重建作文资产。

用途：
1. 按叶子子类重建唯一正式模板
2. 为每道作文题重建唯一正式范文

用法：
    cd backend
    . .venv/bin/activate
    python scripts/rebuild_writing_official_assets.py
    python scripts/rebuild_writing_official_assets.py --task-limit 20
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

ROOT = Path(__file__).resolve().parents[1]
import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import models  # noqa: F401
from app.database import async_session_factory, init_db
from app.models.writing import WritingSample, WritingTask, WritingTemplate
from app.services.writing_service import WritingService


def _report_path() -> Path:
    logs_dir = ROOT.parent / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return logs_dir / f"writing_official_rebuild_{timestamp}.json"


async def rebuild(
    category_limit: int | None = None,
    task_limit: int | None = None,
    concurrency: int = 2,
    reclassify: bool = True,
    needs_rebuild_only: bool = False,
    task_ids: list[int] | None = None,
    refresh_templates: bool = True,
) -> None:
    await init_db()

    async with async_session_factory() as session:
        service = WritingService(session)
        result = await session.execute(
            select(WritingTask)
            .options(
                selectinload(WritingTask.paper),
                selectinload(WritingTask.category),
                selectinload(WritingTask.major_category),
                selectinload(WritingTask.group_category),
                selectinload(WritingTask.samples),
            )
            .where(WritingTask.category_id.isnot(None))
            .order_by(WritingTask.category_id.asc(), WritingTask.id.asc())
        )
        tasks = list(result.scalars().all())
        if task_ids:
            task_id_set = set(task_ids)
            tasks = [task for task in tasks if task.id in task_id_set]
        template_result = await session.execute(
            select(WritingTemplate).options(selectinload(WritingTemplate.category))
        )
        template_by_category = {
            template.category_id: template
            for template in template_result.scalars().all()
            if template.category_id is not None
        }

        if needs_rebuild_only:
            filtered_tasks: list[WritingTask] = []
            for task in tasks:
                template = template_by_category.get(task.category_id)
                if template is None:
                    filtered_tasks.append(task)
                    continue
                sample = service._select_official_sample(
                    task.samples,
                    template=template,
                    expected_template_id=template.id,
                )
                if sample is None:
                    filtered_tasks.append(task)
            tasks = filtered_tasks

    if task_limit is not None:
        tasks = tasks[:task_limit]

    category_anchor_map: dict[int, WritingTask] = {}
    for task in tasks:
        if task.category_id and task.category_id not in category_anchor_map:
            category_anchor_map[task.category_id] = task

    category_items = list(category_anchor_map.items())
    if category_limit is not None:
        category_items = category_items[:category_limit]

    if refresh_templates:
        print(f"开始重建正式模板，共 {len(category_items)} 个子类...")
        for index, (category_id, anchor_task) in enumerate(category_items, start=1):
            async with async_session_factory() as session:
                service = WritingService(session)
                result = await session.execute(
                    select(WritingTask)
                    .options(
                        selectinload(WritingTask.paper),
                        selectinload(WritingTask.category),
                        selectinload(WritingTask.major_category),
                        selectinload(WritingTask.group_category),
                    )
                    .where(WritingTask.id == anchor_task.id)
                )
                anchor = result.scalar_one()
                template = await service.get_or_create_template(
                    category_id,
                    anchor_task=anchor,
                    force_refresh=True,
                    refresh_if_stale=True,
                )
                print(f"[模板 {index}/{len(category_items)}] {anchor.category.path} -> template_id={template.id}")
    else:
        print(f"跳过模板刷新，直接重建正式范文，共 {len(tasks)} 道作文...")

    print(f"开始重建正式范文，共 {len(tasks)} 道作文...")
    semaphore = asyncio.Semaphore(max(1, concurrency))
    lock = asyncio.Lock()
    processed = 0
    success = 0
    failed = 0
    failures: list[dict[str, object]] = []

    async def rebuild_task(task_id: int) -> None:
        nonlocal processed, success, failed
        async with semaphore:
            async with async_session_factory() as session:
                service = WritingService(session)
                try:
                    if reclassify:
                        category_result = await service.classify_task(task_id)
                        if not category_result.success:
                            raise ValueError(category_result.error or "作文重分类失败")
                        await session.commit()
                    task_obj, template, sample = await service.ensure_task_assets(
                        task_id,
                        force_template_refresh=False,
                        regenerate_sample=True,
                    )
                    async with lock:
                        processed += 1
                        success += 1
                        print(
                            f"[范文 {processed}/{len(tasks)}] task_id={task_obj.id} "
                            f"category={task_obj.category.path if task_obj.category else '-'} "
                            f"template_id={template.id} sample_id={sample.id} "
                            f"words={sample.word_count}"
                        )
                except Exception as exc:
                    async with lock:
                        processed += 1
                        failed += 1
                        failures.append({"task_id": task_id, "error": str(exc)})
                        print(f"[范文 {processed}/{len(tasks)}] task_id={task_id} 失败: {exc}")

    await asyncio.gather(*(rebuild_task(task.id) for task in tasks))

    async with async_session_factory() as session:
        summary_row = await session.execute(
            select(
                WritingTask.id,
            ).where(WritingTask.category_id.isnot(None))
        )
        task_count = len(summary_row.scalars().all())
        sample_count = await session.scalar(select(func.count()).select_from(WritingSample))
        stale_versions = await session.scalar(
            select(func.count())
            .select_from(WritingTask)
            .join(WritingSample, WritingSample.task_id == WritingTask.id)
            .join(WritingTemplate, WritingTemplate.id == WritingSample.template_id)
            .where(func.ifnull(WritingSample.template_version, 0) != func.ifnull(WritingTemplate.template_version, 0))
        )
        bad_samples = await session.scalar(
            select(func.count())
            .select_from(WritingSample)
            .where(
                (WritingSample.quality_status.is_(None)) | (WritingSample.quality_status != "passed") |
                (WritingSample.generation_mode.is_(None)) | (WritingSample.generation_mode != "slot_fill") |
                (WritingSample.translation.is_(None)) | (func.trim(WritingSample.translation) == "")
            )
        )

    report = {
        "task_count": task_count or 0,
        "sample_count": sample_count or 0,
        "stale_versions": stale_versions or 0,
        "bad_samples": bad_samples or 0,
        "success": success,
        "failed": failed,
        "failures": failures,
    }
    report_path = _report_path()
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("作文正式资产重建完成")
    print(f"成功 {success}，失败 {failed}")
    print(f"报告已写入: {report_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="重建作文唯一正式模板与正式范文")
    parser.add_argument("--category-limit", type=int, default=None, help="只重建前 N 个子类模板")
    parser.add_argument("--task-limit", type=int, default=None, help="只重建前 N 道作文题")
    parser.add_argument("--concurrency", type=int, default=2, help="范文重建并发数")
    parser.add_argument("--skip-reclassify", action="store_true", help="跳过逐题重分类")
    parser.add_argument("--needs-rebuild-only", action="store_true", help="只重建没有合格正式范文的作文题")
    parser.add_argument("--task-ids", type=str, default="", help="指定 task_id，逗号分隔")
    parser.add_argument("--skip-template-refresh", action="store_true", help="跳过模板刷新，只重建正式范文")
    args = parser.parse_args()
    task_ids = [int(item) for item in args.task_ids.split(",") if item.strip()]
    asyncio.run(
        rebuild(
            category_limit=args.category_limit,
            task_limit=args.task_limit,
            concurrency=args.concurrency,
            reclassify=not args.skip_reclassify,
            needs_rebuild_only=args.needs_rebuild_only,
            task_ids=task_ids or None,
            refresh_templates=not args.skip_template_refresh,
        )
    )


if __name__ == "__main__":
    main()
