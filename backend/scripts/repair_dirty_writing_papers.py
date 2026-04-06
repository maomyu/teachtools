#!/usr/bin/env python3
"""
修复历史作文脏数据：
- 识别一条 writing_task 中同时混入“题目① / 题目②”的旧试卷
- 从试卷库重新提取作文小题
- 重建该试卷下的 writing_tasks / writing_samples

用法：
    cd backend
    . .venv/bin/activate
    python scripts/repair_dirty_writing_papers.py
    python scripts/repair_dirty_writing_papers.py --limit 5
    python scripts/repair_dirty_writing_papers.py --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import select


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import async_session_factory  # noqa: E402
from app.models.paper import ExamPaper  # noqa: E402
from app.models.writing import WritingTask  # noqa: E402
from app.services.llm_parser import LLMDocumentParser  # noqa: E402
from scripts.backfill_writing_tasks import (  # noqa: E402
    LOG_DIR,
    build_source_index,
    extract_tasks_for_file,
    is_dirty_writing_task_content,
    normalize_filename,
    pick_best_source,
    rebuild_paper_writing,
)


@dataclass
class RepairResult:
    paper_id: int
    filename: str
    source_path: str
    old_count: int
    new_count: int = 0
    status: str = "pending"
    error: str = ""


async def repair_dirty_papers(limit: Optional[int], dry_run: bool) -> dict:
    parser = LLMDocumentParser()
    source_index = build_source_index()
    results: list[RepairResult] = []

    async with async_session_factory() as session:
        papers_result = await session.execute(
            select(ExamPaper).order_by(ExamPaper.id)
        )
        papers = papers_result.scalars().all()

        for paper in papers:
            tasks_result = await session.execute(
                select(WritingTask).where(WritingTask.paper_id == paper.id).order_by(WritingTask.id)
            )
            tasks = tasks_result.scalars().all()
            if not tasks:
                continue
            if not any(is_dirty_writing_task_content(task.task_content or "") for task in tasks):
                continue

            matches = source_index.get(normalize_filename(paper.filename), [])
            source_path = pick_best_source(matches, paper)
            if not source_path:
                continue

            results.append(
                RepairResult(
                    paper_id=paper.id,
                    filename=paper.filename,
                    source_path=str(source_path),
                    old_count=len(tasks),
                )
            )

        if limit:
            results = results[:limit]

        for item in results:
            paper = await session.get(ExamPaper, item.paper_id)
            if not paper:
                item.status = "failed"
                item.error = "试卷不存在"
                print(f"[脏卷修复] paper_id={item.paper_id} 失败: 试卷不存在")
                continue

            try:
                tasks = await extract_tasks_for_file(parser, Path(item.source_path))
                if dry_run:
                    item.new_count = len(tasks)
                    item.status = "dry_run"
                    print(f"[脏卷修复] paper_id={item.paper_id} dry-run old={item.old_count} new={item.new_count}")
                    continue

                created_ids = await rebuild_paper_writing(
                    session,
                    paper,
                    tasks,
                    generate_assets=False,
                )
                item.new_count = len(created_ids)
                item.status = "success"
                print(f"[脏卷修复] paper_id={item.paper_id} success old={item.old_count} new={item.new_count}")
            except Exception as exc:
                await session.rollback()
                item.status = "failed"
                item.error = str(exc)
                print(f"[脏卷修复] paper_id={item.paper_id} 失败: {exc}")

    summary = {
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "dry_run": dry_run,
        "total_targets": len(results),
        "success_count": sum(1 for item in results if item.status == "success"),
        "failed_count": sum(1 for item in results if item.status == "failed"),
        "dry_run_count": sum(1 for item in results if item.status == "dry_run"),
        "results": [asdict(item) for item in results],
    }
    return summary


def save_summary(summary: dict) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / f"dirty_writing_repair_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="修复历史作文脏数据")
    parser.add_argument("--limit", type=int, default=None, help="只处理前 N 份试卷")
    parser.add_argument("--dry-run", action="store_true", help="仅扫描，不落库")
    args = parser.parse_args()

    summary = asyncio.run(repair_dirty_papers(limit=args.limit, dry_run=args.dry_run))
    summary_path = save_summary(summary)

    print("=" * 80)
    print("历史作文脏数据修复完成")
    print("=" * 80)
    print(f"目标试卷: {summary['total_targets']}")
    print(f"成功: {summary['success_count']}")
    print(f"失败: {summary['failed_count']}")
    if args.dry_run:
        print(f"dry-run: {summary['dry_run_count']}")
    print(f"日志: {summary_path}")

    if summary["failed_count"]:
        print("\n失败试卷：")
        for item in summary["results"]:
            if item["status"] == "failed":
                print(f"- paper_id={item['paper_id']} {item['filename']} -> {item['error']}")


if __name__ == "__main__":
    main()
