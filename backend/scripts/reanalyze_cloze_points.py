#!/usr/bin/env python
"""
完形填空考点重新分析脚本

功能：
1. 查询考点（可指定条件）
2. 调用 AI 重新分析（支持三维度分析、课本释义等新字段）
3. 更新数据库记录
4. 显示分析进度和结果统计
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, text, or_
from app.database import async_session
from app.models.cloze import ClozePoint, ClozePassage
from app.services.cloze_analyzer import ClozeAnalyzer
import json


async def reanalyze_cloze_points(
    limit: int = None,
    force_all: bool = False,
    only_missing: bool = True
):
    """
    重新分析完形填空考点

    Args:
        limit: 限制处理的数量（用于测试）
        force_all: 强制重新分析所有考点
        only_missing: 只分析缺少新字段的考点（默认）
    """
    print("=" * 60)
    print("完形填空考点重新分析（增强版）")
    print("=" * 60)

    # 初始化分析器
    try:
        analyzer = ClozeAnalyzer()
        print("✓ AI 分析器初始化成功\n")
    except ValueError as e:
        print(f"✗ AI 分析器初始化失败: {e}")
        print("请检查 .env 文件中的 DASHSCOPE_API_KEY 是否配置\n")
        return

    async with async_session() as session:
        # 构建查询
        if force_all:
            # 强制重新分析所有考点
            query = select(ClozePoint)
            print("模式: 重新分析所有考点")
        elif only_missing:
            # 只分析缺少新字段的考点（phrase, word_analysis, textbook_meaning 都为空）
            query = select(ClozePoint).where(
                or_(
                    ClozePoint.point_type == None,
                    ClozePoint.word_analysis == None,
                )
            )
            print("模式: 只分析缺少新字段的考点")
        else:
            # 默认：只分析 point_type 为 NULL 的
            query = select(ClozePoint).where(ClozePoint.point_type == None)
            print("模式: 只分析未分类的考点")

        if limit:
            query = query.limit(limit)
            print(f"限制: {limit} 个考点\n")

        result = await session.execute(query)
        points = result.scalars().all()

        if not points:
            print("没有需要重新分析的考点")
            return

        total = len(points)
        print(f"找到 {total} 个需要重新分析的考点\n")

        # 统计信息
        success_count = 0
        fail_count = 0
        type_distribution = {
            "固定搭配": 0,
            "词义辨析": 0,
            "熟词僻义": 0
        }

        # 遍历每个考点
        for idx, point in enumerate(points, 1):
            print(f"[{idx}/{total}] 分析第 {point.blank_number} 空: {point.correct_word}")

            try:
                # 获取文章内容
                passage_result = await session.execute(
                    select(ClozePassage).where(ClozePassage.id == point.cloze_id)
                )
                passage = passage_result.scalar_one_or_none()

                if not passage:
                    print(f"  ✗ 找不到关联的文章 (cloze_id={point.cloze_id})")
                    fail_count += 1
                    continue

                # 解析选项
                options = json.loads(point.options) if point.options else {}

                # 调用 AI 分析（传入 db_session 支持课本释义查询）
                analysis = await analyzer.analyze_point(
                    blank_number=point.blank_number,
                    correct_word=point.correct_word or "",
                    options=options,
                    context=passage.content,
                    db_session=session  # 支持课本释义查询
                )

                if analysis.success:
                    # 更新基础字段
                    point.point_type = analysis.point_type
                    point.translation = analysis.translation
                    point.explanation = analysis.explanation

                    # 更新通用字段
                    if analysis.confusion_words:
                        point.confusion_words = json.dumps(
                            analysis.confusion_words,
                            ensure_ascii=False
                        )
                    if analysis.tips:
                        point.tips = analysis.tips

                    # 固定搭配专用字段
                    if analysis.phrase:
                        point.phrase = analysis.phrase
                    if analysis.similar_phrases:
                        point.similar_phrases = json.dumps(
                            analysis.similar_phrases,
                            ensure_ascii=False
                        )

                    # 词义辨析专用字段
                    if analysis.word_analysis:
                        point.word_analysis = json.dumps(
                            analysis.word_analysis,
                            ensure_ascii=False
                        )
                    if analysis.dictionary_source:
                        point.dictionary_source = analysis.dictionary_source

                    # 熟词僻义专用字段
                    if analysis.textbook_meaning:
                        point.textbook_meaning = analysis.textbook_meaning
                    if analysis.textbook_source:
                        point.textbook_source = analysis.textbook_source
                    if analysis.context_meaning:
                        point.context_meaning = analysis.context_meaning
                    if analysis.similar_words:
                        point.similar_words = json.dumps(
                            analysis.similar_words,
                            ensure_ascii=False
                        )

                    # 统计
                    success_count += 1
                    type_distribution[analysis.point_type] = type_distribution.get(analysis.point_type, 0) + 1

                    print(f"  ✓ 类型: {analysis.point_type}")
                    if analysis.translation:
                        print(f"    翻译: {analysis.translation}")
                    # 显示扩展信息
                    if analysis.phrase:
                        print(f"    短语: {analysis.phrase}")
                    if analysis.textbook_meaning:
                        print(f"    课本释义: {analysis.textbook_meaning}")
                else:
                    fail_count += 1
                    print(f"  ✗ 分析失败: {analysis.error}")

            except Exception as e:
                fail_count += 1
                print(f"  ✗ 处理异常: {e}")

            # 每10个提交一次
            if idx % 10 == 0:
                await session.commit()
                print(f"  → 已提交 {idx} 个考点\n")

        # 最终提交
        await session.commit()

    # 打印统计结果
    print("\n" + "=" * 60)
    print("分析完成!")
    print("=" * 60)
    print(f"总计: {total} 个考点")
    print(f"成功: {success_count} 个")
    print(f"失败: {fail_count} 个")
    print(f"\n考点类型分布:")
    for point_type, count in type_distribution.items():
        if count > 0:
            print(f"  - {point_type}: {count} 个")
    print("=" * 60)


async def check_status():
    """检查当前数据库状态"""
    print("=" * 60)
    print("数据库状态检查")
    print("=" * 60)

    async with async_session() as session:
        # 统计考点类型分布
        query = text("""
            SELECT
                COALESCE(point_type, 'NULL') as type,
                COUNT(*) as count
            FROM cloze_points
            GROUP BY point_type
            ORDER BY count DESC;
        """)
        result = await session.execute(query)
        rows = result.fetchall()

        print("\n考点类型分布:")
        total = 0
        for row in rows:
            print(f"  {row[0]}: {row[1]} 个")
            total += row[1]

        # 检查新字段填充情况
        print("\n新字段填充情况:")
        new_fields = ['phrase', 'similar_phrases', 'word_analysis', 'textbook_meaning', 'tips']
        for field in new_fields:
            query = text(f"""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN {field} IS NOT NULL AND {field} != '' THEN 1 ELSE 0 END) as filled
                FROM cloze_points
            """)
            result = await session.execute(query)
            row = result.fetchone()
            print(f"  {field}: {row[1]}/{row[0]} 填充")

        print(f"\n总考点数: {total}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="重新分析完形填空考点")
    parser.add_argument(
        "--limit",
        type=int,
        help="限制处理数量（用于测试）"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="只检查数据库状态，不执行分析"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="强制重新分析所有考点（包括已有类型的）"
    )
    parser.add_argument(
        "--missing",
        action="store_true",
        default=True,
        help="只分析缺少新字段的考点（默认行为）"
    )

    args = parser.parse_args()

    if args.check:
        asyncio.run(check_status())
    else:
        asyncio.run(reanalyze_cloze_points(
            limit=args.limit,
            force_all=args.all,
            only_missing=args.missing and not args.all
        ))
