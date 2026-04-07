"""
补齐模板版本不匹配的范文 — 删旧重新生成

原因：模板迭代后版本号升级，旧范文的 rendered_slots_json 与新模板 schema 不兼容，
导致 _sample_meets_quality_bar 判定不通过，前端显示"正在补齐"。

做法：删旧范文 → 按当前模板重新生成。
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from app.database import async_session_factory
from app.services.writing_service import WritingService
from sqlalchemy import select, delete
from app.models.writing import WritingSample, WritingTemplate


async def get_mismatched_task_ids() -> list[int]:
    """查出所有缺少范文的 task_id"""
    import sqlite3
    conn = sqlite3.connect("backend/database/teaching.db")
    rows = conn.execute("""
        select wt.id
        from writing_tasks wt
        where not exists (select 1 from writing_samples ws where ws.task_id = wt.id)
        order by wt.id
    """).fetchall()
    conn.close()
    return [r[0] for r in rows]


async def main():
    task_ids = await get_mismatched_task_ids()
    print(f"需要重生成的范文数: {len(task_ids)}")

    success = 0
    fail = 0

    async with async_session_factory() as db:
        svc = WritingService(db)

        for i, task_id in enumerate(task_ids, 1):
            # 删旧范文
            await db.execute(
                delete(WritingSample).where(WritingSample.task_id == task_id)
            )
            await db.flush()

            try:
                sample = await svc.generate_sample(task_id, score_level="一档")
                success += 1
                print(f"  [{i}/{len(task_ids)}] task_id={task_id} -> sample_id={sample.id}, {sample.word_count}词")
            except Exception as e:
                fail += 1
                print(f"  [{i}/{len(task_ids)}] task_id={task_id} 失败: {e}")

            # 每批提交一次，避免超长事务
            if i % 10 == 0:
                await db.commit()
                print(f"  --- 已提交 {i} 条 ---")

        await db.commit()

    print(f"\n补齐完成: 成功 {success} 条, 失败 {fail} 条")


if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    asyncio.run(main())
