"""
批量为现有作文提取话题

用法: python -m scripts.extract_writing_topics
或: cd backend && python scripts/extract_writing_topics.py
"""
import asyncio
import sys
import logging
from pathlib import Path

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.database import async_session_factory
from app.models.writing import WritingTask
from app.services.writing_topic_classifier import WritingTopicClassifier


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def extract_topics(batch_size: int = 50, dry_run: bool = False):
    """
    批量提取作文话题

    Args:
        batch_size: 每批处理的数量
        dry_run: 仅预览，不实际修改数据库
    """
    classifier = WritingTopicClassifier()

    async with async_session_factory() as db:
        # 查找没有话题的作文
        result = await db.execute(
            select(WritingTask).where(
                (WritingTask.primary_topic.is_(None)) |
                (WritingTask.primary_topic == "")
            ).order_by(WritingTask.id)
        )
        tasks = result.scalars().all()

        total = len(tasks)
        if total == 0:
            logger.info("所有作文都已有话题，无需处理")
            return

        logger.info(f"找到 {total} 篇未分类话题的作文")

        if dry_run:
            logger.info("=== DRY RUN 模式 - 仅预览 ===")
            for i, task in enumerate(tasks[:10]):  # 只显示前10条
                logger.info(f"[{i+1}] task_id={task.id}")
                logger.info(f"    内容: {task.task_content[:80]}...")
            logger.info(f"... 还有 {total - 10} 条记录")
            return

        # 实际处理
        success_count = 0
        fail_count = 0
        failed_ids = []

        for i, task in enumerate(tasks):
            logger.info(f"[{i+1}/{total}] 处理: task_id={task.id}")

            try:
                # 使用同步方法
                topic_result = await asyncio.to_thread(
                    classifier.classify_sync,
                    content=task.task_content,
                    requirements=task.requirements or ""
                )

                if topic_result.success and topic_result.primary_topic:
                    task.primary_topic = topic_result.primary_topic
                    logger.info(f"  -> 话题: {topic_result.primary_topic} (confidence: {topic_result.confidence:.2f})")
                    success_count += 1
                else:
                    logger.warning(f"  -> 失败: {topic_result.error}")
                    fail_count += 1
                    failed_ids.append(task.id)

                # 每批提交一次
                if (i + 1) % batch_size == 0:
                    await db.commit()
                    logger.info(f"  已提交 {i + 1} 条记录")

            except Exception as e:
                logger.error(f"  -> 异常: {e}")
                fail_count += 1
                failed_ids.append(task.id)

            # 避免API限流
            await asyncio.sleep(0.3)

        # 提交剩余的更改
        await db.commit()

        # 输出统计
        logger.info("=" * 50)
        logger.info(f"处理完成!")
        logger.info(f"  成功: {success_count}")
        logger.info(f"  失败: {fail_count}")

        if failed_ids:
            logger.info(f"  失败 ID: {failed_ids}")
            logger.info(f"  可使用以下命令重试失败的记录:")
            logger.info(f"    python -m scripts.extract_writing_topics --retry {','.join(map(str, failed_ids))}")


async def retry_failed(task_ids: list[int]):
    """重试失败的记录"""
    classifier = WritingTopicClassifier()

    async with async_session_factory() as db:
        result = await db.execute(
            select(WritingTask).where(WritingTask.id.in_(task_ids))
        )
        tasks = result.scalars().all()

        logger.info(f"重试 {len(tasks)} 条记录")

        success_count = 0
        for i, task in enumerate(tasks):
            logger.info(f"[{i+1}/{len(tasks)}] 重试: task_id={task.id}")

            try:
                topic_result = await asyncio.to_thread(
                    classifier.classify_sync,
                    content=task.task_content,
                    requirements=task.requirements or ""
                )

                if topic_result.success and topic_result.primary_topic:
                    task.primary_topic = topic_result.primary_topic
                    logger.info(f"  -> 话题: {topic_result.primary_topic}")
                    success_count += 1
                else:
                    logger.warning(f"  -> 仍失败: {topic_result.error}")

                await db.commit()

            except Exception as e:
                logger.error(f"  -> 异常: {e}")

            await asyncio.sleep(0.3)

        logger.info(f"重试完成: {success_count}/{len(tasks)} 成功")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="批量提取作文话题")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不修改数据库")
    parser.add_argument("--batch-size", type=int, default=50, help="每批处理的数量")
    parser.add_argument("--retry", type=str, help="重试失败的记录，传入逗号分隔的 ID 列表")

    args = parser.parse_args()

    if args.retry:
        task_ids = [int(x.strip()) for x in args.retry.split(",")]
        asyncio.run(retry_failed(task_ids))
    else:
        asyncio.run(extract_topics(
            batch_size=args.batch_size,
            dry_run=args.dry_run
        ))


if __name__ == "__main__":
    main()
