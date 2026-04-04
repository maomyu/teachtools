# 蟥 Failed task IDs
FAILED_IDS="113 141 147 254 266 316 364 437 447 522 540 545 566 575 588 595 620 624 641 645 665 708 759 779 804 846 849 872 8849 989 1175 1176"

echo "补跑 $(( id in FAILED_IDS )) 条失败任务, concurrency=1)..."

success=0
fail=0

results = []

async def main():
    async with get_session_local() as db:
        svc = WritingService(db)
        for i, task_id in enumerate(FAILED_IDS, 1):
            # 删旧范文
            from app.models.writing import WritingSample
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
                print(f'  [{i}/{len(FAILED_IDS)}] task_id={task_id} 失败: {e}')
        await db.commit()
    print(f'补跑完成: 成功 {success} 条, 失败 {fail} 条")

asyncio.run(main())
