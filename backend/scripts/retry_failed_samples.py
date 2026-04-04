"""补跑失败的范文生成任务"""
import asyncio
import sys

sys.path.insert(0, ".")

from app.database import async_session
from app.services.writing_service import WritingService
from sqlalchemy import select
from app.models.writing import WritingSample

FAILED_IDS = [
    113,141,254,266,316,437,447,522,540,575,588,
    595,620,624,641,645,665,708,759,779,846,849,872,883,891,
    918,930,943,949,1175,1176,
]


async def main():
    print(f"补跑 {len(FAILED_IDS)} 条失败任务 (并发=1)...")
    success = 0
    fail = 0

    async with async_session() as db:
        svc = WritingService(db)
        for i, task_id in enumerate(FAILED_IDS, 1):
            # 删旧范文
            old_samples = (await db.execute(
                select(WritingSample).where(WritingSample.task_id == task_id)
            )).scalars().all()
            for s in old_samples:
                await db.delete(s)
            await db.flush()

            try:
                sample = await svc.generate_sample(task_id, score_level="一档")
                success += 1
                print(f"  [{i}/{len(FAILED_IDS)}] task_id={task_id} -> sample_id={sample.id}, {sample.word_count}词")
            except Exception as e:
                fail += 1
                print(f"  [{i}/{len(FAILED_IDS)}] task_id={task_id} 失败: {e}")

        await db.commit()

    print(f"\n补跑完成: 成功 {success} 条, 失败 {fail} 条")


if __name__ == "__main__":
    asyncio.run(main())
