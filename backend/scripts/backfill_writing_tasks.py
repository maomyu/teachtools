#!/usr/bin/env python3
"""
批量补齐历史试卷缺失的作文小题，并为每道作文生成子类、模板和范文。

用法：
    cd backend
    . .venv/bin/activate
    python scripts/backfill_writing_tasks.py
    python scripts/backfill_writing_tasks.py --paper-id 921
    python scripts/backfill_writing_tasks.py --limit 20
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import delete, func, select


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import async_session_factory  # noqa: E402
from app.models.paper import ExamPaper  # noqa: E402
from app.models.writing import WritingSample, WritingTask  # noqa: E402
from app.services.llm_parser import (  # noqa: E402
    LLMDocumentParser,
    WritingExtractTask,
    dedupe_writing_tasks,
)
from app.services.writing_service import WritingService  # noqa: E402
from scripts.import_papers_via_frontend import infer_source_expectations  # noqa: E402


DOCX_ROOT = REPO_ROOT / "试卷库"
LOG_DIR = REPO_ROOT / "logs"


@dataclass
class BackfillResult:
    paper_id: int
    filename: str
    source_path: str
    expected_count: int
    old_count: int
    new_count: int = 0
    status: str = "pending"
    error: str = ""
    task_ids: list[int] = field(default_factory=list)


def normalize_filename(name: str) -> str:
    normalized = Path(name).name.strip()
    if normalized.startswith("区校试卷_"):
        parts = normalized.split("_", 4)
        if len(parts) == 5 and parts[4]:
            normalized = parts[4]
    normalized = normalized.replace("（", "(").replace("）", ")")
    return re.sub(r"\s+", "", normalized)


def build_source_index() -> dict[str, list[Path]]:
    index: dict[str, list[Path]] = defaultdict(list)
    for path in DOCX_ROOT.rglob("*.docx"):
        index[normalize_filename(path.name)].append(path)
    return index


def pick_best_source(matches: list[Path], paper: ExamPaper) -> Optional[Path]:
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]

    def score(path: Path) -> int:
        path_str = str(path)
        score_value = 0
        for value in (paper.year, paper.region, paper.grade, paper.exam_type):
            if value and str(value) in path_str:
                score_value += 1
        return score_value

    return sorted(matches, key=score, reverse=True)[0]


async def extract_tasks_for_file(parser: LLMDocumentParser, file_path: Path) -> list[WritingExtractTask]:
    tasks = parser._extract_writing_tasks_from_docx(str(file_path))
    if tasks:
        return dedupe_writing_tasks(tasks)

    fileid = await parser.upload_file(str(file_path))
    result = await parser.extract_writing(fileid, file_path=str(file_path))
    if not result.success:
        raise ValueError(result.error or "作文提取失败")
    return dedupe_writing_tasks(result.tasks)


async def rebuild_paper_writing(
    session,
    paper: ExamPaper,
    tasks: list[WritingExtractTask],
) -> list[int]:
    service = WritingService(session)

    existing_tasks_result = await session.execute(
        select(WritingTask.id).where(WritingTask.paper_id == paper.id)
    )
    existing_task_ids = [row[0] for row in existing_tasks_result.all()]
    if existing_task_ids:
        await session.execute(delete(WritingSample).where(WritingSample.task_id.in_(existing_task_ids)))
        await session.execute(delete(WritingTask).where(WritingTask.id.in_(existing_task_ids)))
        await session.flush()

    created_ids: list[int] = []
    for extracted_task in tasks:
        task = WritingTask(
            paper_id=paper.id,
            task_content=extracted_task.content,
            requirements=extracted_task.requirements,
            word_limit=extracted_task.word_limit,
            grade=paper.grade,
            semester=paper.semester,
            exam_type=paper.exam_type,
        )
        session.add(task)
        await session.flush()

        await service.classify_task(
            task,
            extracted_writing_type=extracted_task.writing_type,
            extracted_application_type=extracted_task.application_type,
        )
        await service.ensure_task_assets(
            task,
            force_template_refresh=False,
            regenerate_sample=False,
            score_level="一档",
        )
        created_ids.append(task.id)

    await session.commit()
    return created_ids


async def backfill(limit: Optional[int], paper_id: Optional[int], dry_run: bool) -> dict:
    source_index = build_source_index()
    parser = LLMDocumentParser()
    results: list[BackfillResult] = []

    async with async_session_factory() as session:
        query = (
            select(ExamPaper, func.count(WritingTask.id).label("writing_count"))
            .outerjoin(WritingTask, WritingTask.paper_id == ExamPaper.id)
            .group_by(ExamPaper.id)
            .order_by(ExamPaper.id)
        )
        if paper_id:
            query = query.where(ExamPaper.id == paper_id)

        rows = (await session.execute(query)).all()

        for paper, writing_count in rows:
            matches = source_index.get(normalize_filename(paper.filename), [])
            source_path = pick_best_source(matches, paper)
            if not source_path:
                continue

            expectations = infer_source_expectations(source_path)
            if not expectations.get("expects_writing"):
                continue

            local_tasks = parser._extract_writing_tasks_from_docx(str(source_path))
            expected_count = max(1, len(local_tasks)) if local_tasks else 1

            if writing_count == expected_count:
                continue

            results.append(
                BackfillResult(
                    paper_id=paper.id,
                    filename=paper.filename,
                    source_path=str(source_path),
                    expected_count=expected_count,
                    old_count=int(writing_count or 0),
                )
            )

        if limit:
            results = results[:limit]

        for item in results:
            paper = await session.get(ExamPaper, item.paper_id)
            if not paper:
                item.status = "failed"
                item.error = "试卷不存在"
                continue

            try:
                tasks = await extract_tasks_for_file(parser, Path(item.source_path))
                if not tasks:
                    raise ValueError("未提取到作文题")

                item.expected_count = len(tasks)
                if dry_run:
                    item.new_count = len(tasks)
                    item.status = "dry_run"
                    continue

                created_ids = await rebuild_paper_writing(session, paper, tasks)
                item.new_count = len(created_ids)
                item.task_ids = created_ids
                item.status = "success"
            except Exception as exc:
                await session.rollback()
                item.status = "failed"
                item.error = str(exc)

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
    path = LOG_DIR / f"writing_backfill_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="补齐历史缺失作文小题")
    parser.add_argument("--limit", type=int, default=None, help="只处理前 N 份试卷")
    parser.add_argument("--paper-id", type=int, default=None, help="只处理指定试卷 ID")
    parser.add_argument("--dry-run", action="store_true", help="仅扫描，不落库")
    args = parser.parse_args()

    summary = asyncio.run(backfill(limit=args.limit, paper_id=args.paper_id, dry_run=args.dry_run))
    summary_path = save_summary(summary)

    print("=" * 80)
    print("作文补齐完成")
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
