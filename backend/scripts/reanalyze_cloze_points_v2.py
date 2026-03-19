#!/usr/bin/env python
"""
批量重新分析完形填空考点（使用 V5 分析器 - 全信号扫描 + 动态维度）

用法:
    python scripts/reanalyze_cloze_points_v2.py [--limit N] [--dry-run]

选项:
    --limit N       : 限制处理的考点数量
    --dry-run      : 仅预览模式，不实际写入数据库
"""

import asyncio
import sys
from pathlib import Path

from sqlalchemy import select
from app.database import async_session
from app.models.cloze import (
    ClozePassage,
    ClozePoint,
    PointTypeDefinition,
)
from app.models.cloze import ClozeSecondaryPoint, ClozeRejectionPoint
from app.services.cloze_analyzer import ClozeAnalyzerV5


from app.services.cloze_analyzer import NEW_CODE_TO_LEGACY


from sqlalchemy.orm import selectinload
import argparse
import json
import time


from datetime import datetime


async def reanalyze_points(limit: int = None, dry_run: bool = False):
    """
    批量重新分析完形考点
    """
    print("=" * 60)
    print("批量重新分析完形填空考点 (V2 - 16种考点)")
    print("=" * 60)

    async with async_session() as session:
        # 获取所有完形文章（包含考点）
        query = (
            select(ClozePassage)
            .options(selectinload(ClozePassage.points))
            .order_by(ClozePassage.id)
        )
        if limit:
            query = query.limit(limit)

        passages = (await session.execute(query)).scalars().all()
        print(f"找到 {len(passages)} 的完形文章")

        total_points = 0
        analyzed = 0
        updated = 0
        failed = 0

        cloze_analyzer = ClozeAnalyzerV5()

        for passage in passages:
            print(f"\n处理文章 ID={passage.id}...")

            for point in passage.points:
                total_points += 1

                try:
                    # 获取完整文章内容
                    full_content = passage.original_content or passage.content

                    # 提取空格附近的上下文（前后各2句），提高分析精准度
                    context = cloze_analyzer.extract_context(full_content, point.blank_number, context_sentences=2)

                    options_dict = json.loads(point.options) if point.options else {}

                    # 调用 V2 分析器
                    analysis = await cloze_analyzer.analyze_point(
                        blank_number=point.blank_number,
                        correct_word=point.correct_word or "",
                        options=options_dict,
                        context=context,
                        db_session=session
                    )

                    if not analysis.success:
                        print(f"  ✗ 空 {point.blank_number}: 分析失败 - {analysis.error}")
                        failed += 1
                        continue

                    # 预览模式
                    if dry_run:
                        print(f"  騡式 - 空 {point.blank_number}:")
                        print(f"    主考点: {analysis.primary_point}")
                        print(f"    辅助考点: {len(analysis.secondary_points)}")
                        print(f"    排错点: {len(analysis.rejection_points)}")
                        continue

                    # 更新主考点编码
                    if analysis.primary_point:
                        point.primary_point_code = analysis.primary_point.get("code")
                        # 更新旧类型（向后兼容）
                        if point.primary_point_code in NEW_CODE_TO_LEGACY:
                            point.point_type = NEW_CODE_TO_LEGACY[point.primary_point_code]
                        else:
                            point.point_type = None

                    # 更新通用字段
                    if analysis.translation:
                        point.translation = analysis.translation
                    if analysis.explanation:
                        point.explanation = analysis.explanation
                    if analysis.confusion_words:
                        point.confusion_words = json.dumps(
analysis.confusion_words, ensure_ascii=False)
                    if analysis.tips:
                        point.tips = analysis.tips

                    # 固定搭配专用字段
                    if analysis.phrase:
                        point.phrase = analysis.phrase
                    if analysis.similar_phrases:
                        point.similar_phrases = json.dumps(analysis.similar_phrases, ensure_ascii=False)

                    # 词义辨析专用字段
                    if analysis.word_analysis:
                        point.word_analysis = json.dumps(analysis.word_analysis, ensure_ascii=False)
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
                        point.similar_words = json.dumps(analysis.similar_words, ensure_ascii=False)

                    # 删除旧的辅助考点和排错点
                    await session.execute(
                        select(ClozeSecondaryPoint).where(
                            ClozeSecondaryPoint.cloze_point_id == point.id
                        )
                    )
                    await session.execute(
                        select(ClozeRejectionPoint).where(
                            ClozeRejectionPoint.cloze_point_id == point.id
                        )
                    )

                    # 添加新的辅助考点
                    if analysis.secondary_points:
                        for idx, sp in enumerate(analysis.secondary_points):
                            sec_point = ClozeSecondaryPoint(
                                cloze_point_id=point.id,
                                point_code=sp.get("point_code"),
                                explanation=sp.get("explanation"),
                                sort_order=idx
                            )
                            session.add(sec_point)

                    # 添加新的排错点（V5 字段）
                    if analysis.rejection_points:
                        for rp in analysis.rejection_points:
                            rejection_code = rp.get("rejection_code") or rp.get("code") or rp.get("point_code") or "D1"
                            rejection_reason = rp.get("rejection_reason") or rp.get("explanation") or ""
                            rej_point = ClozeRejectionPoint(
                                cloze_point_id=point.id,
                                option_word=rp.get("option_word"),
                                point_code=rejection_code,
                                rejection_code=rejection_code,
                                explanation=rejection_reason,
                                rejection_reason=rejection_reason
                            )
                            session.add(rej_point)

                    analyzed += 1
                    updated += 1

                except Exception as e:
                    print(f"  ✗ 空 {point.blank_number}: 更新失败 - {e}")
                    failed += 1
                    await session.rollback()
                    continue

        await session.commit()

    # 打印总结
    print("\n" + "=" * 60)
    print(f"处理完成!")
    print(f"总考点: {total_points}")
    print(f"分析成功: {analyzed}")
    print(f"更新: {updated}")
    print(f"失败: {failed}")
    if failed > 0:
        print(f"错误示例:")
        for p in failed_points:
            print(f"  - {p}")

    print(f"\n耗时: {time.time() - start_time:.2f}s")


async def main():
    parser = argparse.ArgumentParser(description="批量重新分析完形填空考点")
    parser.add_argument("--limit", type=int, default=None, help="限制处理的考点数量")
    parser.add_argument("--dry-run", action="store_true", help="仅预览模式，不实际写入")

    args = parser.parse_args()

    await reanalyze_points(limit=args.limit, dry_run=args.dry_run)


if __name__ == "__main__":
    asyncio.run(main())
