#!/usr/bin/env python3
"""
检查数据库中选项为空的阅读理解题目

用法：
    python backend/scripts/check_empty_options.py           # 检查所有
"""
import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, or_
from app.database import async_session_factory
from app.models.reading import ReadingPassage, Question
from app.models.paper import ExamPaper


async def check_empty_options():
    """检查所有选项为空的题目"""
    async with async_session_factory() as db:
        # 查询所有选项为空的题目
        # 条件：A、B、C、D 四个选项全为空
        query = (
            select(Question, ReadingPassage, ExamPaper)
            .join(ReadingPassage, Question.passage_id == ReadingPassage.id)
            .join(ExamPaper, ReadingPassage.paper_id == ExamPaper.id)
            .where(
                or_(
                    Question.option_a == None,
                    Question.option_a == "",
                )
            )
            .where(
                or_(
                    Question.option_b == None,
                    Question.option_b == "",
                )
            )
            .where(
                or_(
                    Question.option_c == None,
                    Question.option_c == "",
                )
            )
            .where(
                or_(
                    Question.option_d == None,
                    Question.option_d == "",
                )
            )
        )

        result = await db.execute(query)
        rows = result.all()

        if not rows:
            print("✅ 没有发现选项全部为空的题目")
            return

        print(f"⚠️  发现 {len(rows)} 道题目所有选项均为空:\n")

        for question, passage, paper in rows:
            print(f"  - 试卷: {paper.year} {paper.region} {paper.exam_type}")
            print(f"    文章: {passage.passage_type}篇 (ID: {passage.id})")
            print(f"    题目: Q{question.question_number} - {question.question_text[:50]}...")
            print()

        # 按试卷分组统计
        papers_with_issues = {}
        for question, passage, paper in rows:
            if paper.id not in papers_with_issues:
                papers_with_issues[paper.id] = {
                    "info": f"{paper.year} {paper.region} {paper.exam_type}",
                    "count": 0
                }
            papers_with_issues[paper.id]["count"] += 1

        print("\n按试卷统计:")
        for paper_id, info in papers_with_issues.items():
            print(f"  - {info['info']}: {info['count']} 道题目")


async def main():
    """主函数"""
    print("=" * 80)
    print("  阅读理解题目选项检查工具")
    print("=" * 80)
    print()

    await check_empty_options()


if __name__ == "__main__":
    asyncio.run(main())
