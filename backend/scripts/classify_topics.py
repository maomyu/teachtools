#!/usr/bin/env python
"""
批量话题分类脚本

使用通义千问对未分类的文章进行话题分类
"""
import asyncio
import sys
import json
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.database import async_session
from app.models.reading import ReadingPassage
from app.services.ai_service import QwenService


async def classify_passages(
    grade: str = None,
    limit: int = None,
    force: bool = False
):
    """
    批量分类文章话题

    Args:
        grade: 筛选年级
        limit: 限制数量
        force: 强制重新分类（包括已分类的）
    """
    service = QwenService()

    async with async_session() as session:
        # 构建查询
        query = select(ReadingPassage)

        if grade:
            # 需要join papers表获取年级
            from app.models.paper import ExamPaper
            query = query.join(ExamPaper).where(ExamPaper.grade == grade)

        if not force:
            query = query.where(ReadingPassage.primary_topic == None)

        query = query.order_by(ReadingPassage.id)

        result = await session.execute(query)
        passages = result.scalars().all()

        if limit:
            passages = passages[:limit]

        print(f"找到 {len(passages)} 篇待分类文章")
        print("=" * 50)

        success_count = 0
        failed_count = 0

        for i, passage in enumerate(passages, 1):
            print(f"\n[{i}/{len(passages)}] 处理文章 ID={passage.id}")

            try:
                # 获取年级信息
                from app.models.paper import ExamPaper
                paper_result = await session.execute(
                    select(ExamPaper).where(ExamPaper.id == passage.paper_id)
                )
                paper = paper_result.scalar_one_or_none()
                grade_level = paper.grade if paper else "初三"

                # 调用AI分类
                content = passage.content[:2000]  # 限制内容长度
                classify_result = service.classify_topic(content, grade_level)

                if classify_result.get("primary_topic"):
                    passage.primary_topic = classify_result["primary_topic"]
                    # 将列表序列化为JSON字符串
                    secondary = classify_result.get("secondary_topics", [])
                    passage.secondary_topics = json.dumps(secondary, ensure_ascii=False) if secondary else None
                    passage.topic_confidence = classify_result.get("confidence", 0.0)

                    await session.commit()

                    success_count += 1
                    print(f"  ✓ 话题: {passage.primary_topic} (置信度: {passage.topic_confidence})")
                else:
                    failed_count += 1
                    error = classify_result.get("error", "未知错误")
                    print(f"  ✗ 失败: {error}")

            except Exception as e:
                failed_count += 1
                print(f"  ✗ 异常: {str(e)}")

        print("\n" + "=" * 50)
        print("分类完成!")
        print(f"成功: {success_count}")
        print(f"失败: {failed_count}")
        print("=" * 50)


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="批量话题分类")
    parser.add_argument(
        "--grade",
        type=str,
        default=None,
        help="筛选年级（初一/初二/初三）"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="限制处理数量"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制重新分类（包括已分类的）"
    )

    args = parser.parse_args()

    await classify_passages(
        grade=args.grade,
        limit=args.limit,
        force=args.force
    )


if __name__ == "__main__":
    asyncio.run(main())
