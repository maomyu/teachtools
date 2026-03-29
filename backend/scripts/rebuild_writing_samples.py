"""
按新子类模板重建作文范文。

用途：
1. 删除旧的 AI 长篇作文范文
2. 基于新分类树与子类模板，为每条作文重新生成 150 词左右范文

用法：
    cd backend
    . .venv/bin/activate
    python scripts/rebuild_writing_samples.py
    python scripts/rebuild_writing_samples.py --limit 10
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from sqlalchemy import delete, select

ROOT = Path(__file__).resolve().parents[1]
import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import models  # noqa: F401  # 确保模型注册
from app.database import async_session_factory, init_db
from app.models.writing import WritingSample, WritingTask
from app.services.writing_service import WritingService


async def rebuild(
    limit: int | None = None,
    start_id: int | None = None,
    concurrency: int = 4,
    max_attempts: int = 4,
) -> None:
    await init_db()

    async with async_session_factory() as session:
        print("1/3 清空旧作文范文...")
        await session.execute(delete(WritingSample))
        await session.commit()

        query = (
            select(WritingTask.id)
            .where(WritingTask.category_id.isnot(None))
            .order_by(WritingTask.id)
        )
        if start_id is not None:
            query = query.where(WritingTask.id >= start_id)
        if limit is not None:
            query = query.limit(limit)

        result = await session.execute(query)
        task_ids = list(result.scalars().all())

    print(f"2/3 开始重建范文，共 {len(task_ids)} 条作文...")
    success = 0
    failed = 0
    processed = 0
    lock = asyncio.Lock()
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def rebuild_one(task_id: int) -> None:
        nonlocal success, failed, processed
        async with semaphore:
            async with async_session_factory() as session:
                service = WritingService(session)
                try:
                    accepted_sample = None
                    accepted_distance = None

                    for attempt in range(1, max_attempts + 1):
                        sample = await service.generate_sample(task_id, score_level="一档")
                        word_count = sample.word_count or 0
                        distance = abs(word_count - 150)
                        in_target = 130 <= word_count <= 170

                        if accepted_sample is None or distance < (accepted_distance or 10**9):
                            if accepted_sample and accepted_sample.id != sample.id:
                                await session.delete(accepted_sample)
                                await session.commit()
                            accepted_sample = sample
                            accepted_distance = distance
                        else:
                            await session.delete(sample)
                            await session.commit()

                        if in_target:
                            break

                    sample = accepted_sample
                    word_count = sample.word_count if sample else None
                    in_target = bool(word_count is not None and 130 <= word_count <= 170)

                    async with lock:
                        if in_target:
                            success += 1
                        else:
                            failed += 1
                        processed += 1
                        print(
                            f"   [{processed}/{len(task_ids)}] task_id={task_id} -> "
                            f"sample_id={sample.id if sample else '-'}, {word_count}词"
                            f"{'' if in_target else '（未命中目标区间）'}"
                        )
                except Exception as exc:
                    async with lock:
                        failed += 1
                        processed += 1
                        print(f"   [{processed}/{len(task_ids)}] task_id={task_id} 失败: {exc}")

    await asyncio.gather(*(rebuild_one(task_id) for task_id in task_ids))

    print("3/3 重建完成")
    print(f"   成功 {success} 条，失败 {failed} 条")


def main() -> None:
    parser = argparse.ArgumentParser(description="按新子类模板重建作文范文")
    parser.add_argument("--limit", type=int, default=None, help="只重建前 N 条，便于验证")
    parser.add_argument("--start-id", type=int, default=None, help="从指定 task_id 开始重建")
    parser.add_argument("--concurrency", type=int, default=4, help="并发生成数")
    parser.add_argument("--max-attempts", type=int, default=4, help="单题最多重试次数")
    args = parser.parse_args()
    asyncio.run(
        rebuild(
            limit=args.limit,
            start_id=args.start_id,
            concurrency=args.concurrency,
            max_attempts=args.max_attempts,
        )
    )


if __name__ == "__main__":
    main()
