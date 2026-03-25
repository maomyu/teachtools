#!/usr/bin/env python
"""
试卷批量导入脚本

遍历试卷目录，解析并导入数据库
"""
import asyncio
import json
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.database import async_session, engine
from app.models.paper import ExamPaper
from app.models.reading import ReadingPassage
from app.models.topic import Topic
from app.models.cloze import ClozePassage, ClozePoint
from app.services.docx_parser import DocxParser
from app.services.llm_parser import LLMDocumentParser
from app.services.cloze_analyzer import ClozeAnalyzerV5
from app.services.topic_classifier import TopicClassifier
from app.services.text_utils import normalize_cloze_blanks, align_blank_numbers_with_content
from app.services.image_extractor import ImageExtractor


async def get_or_create_paper(
    session,
    filename: str,
    file_path: str,
    metadata: Dict
) -> ExamPaper:
    """获取或创建试卷记录"""
    # 检查是否已存在
    result = await session.execute(
        select(ExamPaper).where(ExamPaper.filename == filename)
    )
    paper = result.scalar_one_or_none()

    if paper:
        return paper

    # 创建新记录
    paper = ExamPaper(
        filename=filename,
        original_path=str(file_path),
        year=metadata.get("year"),
        region=metadata.get("region"),
        school=metadata.get("school"),
        grade=metadata.get("grade"),
        semester=metadata.get("semester"),
        season=metadata.get("season"),
        exam_type=metadata.get("exam_type"),
        version=metadata.get("version", "学生版"),
        import_status="pending"
    )
    session.add(paper)
    await session.flush()

    return paper


async def import_paper(file_path: Path, batch_id: str, use_llm: bool = True) -> Dict:
    """
    导入单个试卷

    完全依赖 AI 解析，不使用正则匹配
    """
    start_time = time.time()
    result = {
        "filename": file_path.name,
        "status": "pending",
        "error": None,
        "passages": 0,
        "cloze_points": 0
    }

    try:
        # 解析文件名获取元数据（仅用于记录，不用于内容提取）
        parser = DocxParser(str(file_path))
        metadata = parser.parse_filename()

        # 从文件路径提取目录结构信息（如果有）
        parent_dir = file_path.parent
        if parent_dir.name in ["东城", "西城", "海淀", "朝阳", "丰台", "石景山",
                               "通州", "顺义", "昌平", "大兴", "房山", "门头沟",
                               "怀柔", "平谷", "密云", "延庆"]:
            metadata["region"] = parent_dir.name

        async with async_session() as session:
            # 创建试卷记录
            paper = await get_or_create_paper(session, file_path.name, file_path, metadata)

            if not use_llm:
                result["status"] = "failed"
                result["error"] = "必须使用 AI 解析模式"
                return result

            # ============================================================================
            #  统一使用 AI 解析文档
            # ============================================================================
            llm_parser = LLMDocumentParser()
            llm_result = await llm_parser.parse_document(str(file_path))

            if not llm_result.success:
                paper.import_status = "failed"
                paper.error_message = llm_result.error
                result["status"] = "failed"
                result["error"] = f"AI解析失败: {llm_result.error}"
                await session.commit()
                return result

            paper.import_status = "completed"
            paper.parse_strategy = "llm"
            paper.confidence = 0.95
            result["status"] = "completed"

            # ============================================================================
            #  提取图片选项并回填到题目结构
            # ============================================================================
            try:
                image_extractor = ImageExtractor()
                option_images, warnings = image_extractor.enrich_passages_with_images(
                    doc_path=str(file_path),
                    paper_id=paper.id,
                    passages=llm_result.passages,
                )
                for warning in warnings:
                    print(f"  ⚠ {warning}")
                if option_images:
                    print(f"  提取了 {len(option_images)} 张选项图片")
            except Exception as e:
                print(f"  ⚠ 图片提取失败（不影响导入）: {e}")

            # 初始化话题分类器（复用实例）
            topic_classifier = TopicClassifier()
            grade = metadata.get("grade") or "初二"

            # ============================================================================
            #  处理阅读文章
            # ============================================================================
            if llm_result.passages:
                for passage_data in llm_result.passages:
                    # 创建阅读文章记录
                    content = passage_data["content"]
                    passage = ReadingPassage(
                        paper_id=paper.id,
                        passage_type=passage_data["passage_type"],
                        content=content,
                        word_count=passage_data.get("word_count") or len(content.split())
                    )
                    session.add(passage)
                    await session.flush()

                    # 调用 AI 分类话题
                    try:
                        topic_result = await topic_classifier.classify(
                            content,
                            grade=grade
                        )
                        if topic_result.success and topic_result.primary_topic:
                            passage.primary_topic = topic_result.primary_topic
                            passage.secondary_topics = json.dumps(
                                topic_result.secondary_topics or [],
                                ensure_ascii=False
                            )
                            passage.topic_confidence = topic_result.confidence
                    except Exception as e:
                        print(f"  ⚠ 阅读文章{passage_data['passage_type']}话题分类失败: {e}")

                    result["passages"] += 1
                    print(f"  ✓ 阅读文章{passage_data['passage_type']}: {passage.primary_topic or '未分类'}")

            # ============================================================================
            #  处理完形填空
            # ============================================================================
            if llm_result.cloze and llm_result.cloze.get("found"):
                cloze_data = llm_result.cloze
                content_with_blanks = cloze_data.get("content_with_blanks", "")
                blanks = cloze_data.get("blanks", [])

                if content_with_blanks and blanks:
                    # 标准化空格格式
                    normalized_content = await normalize_cloze_blanks(
                        content_with_blanks,
                        len(blanks),
                        use_ai_fallback=True
                    )

                    # 创建完形文章记录
                    cloze_passage = ClozePassage(
                        paper_id=paper.id,
                        content=normalized_content,
                        word_count=len(normalized_content.split())
                    )
                    session.add(cloze_passage)
                    await session.flush()

                    # 调用 AI 分类主题
                    try:
                        topic_result = await topic_classifier.classify(
                            normalized_content,
                            grade=grade
                        )
                        if topic_result.success and topic_result.primary_topic:
                            cloze_passage.primary_topic = topic_result.primary_topic
                            cloze_passage.secondary_topics = json.dumps(
                                topic_result.secondary_topics or [],
                                ensure_ascii=False
                            )
                            cloze_passage.topic_confidence = topic_result.confidence
                            print(f"  ✓ 完形主题: {topic_result.primary_topic}")
                    except Exception as e:
                        print(f"  ⚠ 完形主题分类失败: {e}")

                    # 初始化考点分析器 (V5 - 全信号扫描 + 动态维度)
                    cloze_analyzer = ClozeAnalyzerV5()

                    # 遍历每个空格，分析考点并保存
                    aligned_blank_numbers = align_blank_numbers_with_content(
                        normalized_content,
                        [blank.get("blank_number") or 0 for blank in blanks],
                    )

                    for index, blank in enumerate(blanks):
                        blank_number = aligned_blank_numbers[index] if index < len(aligned_blank_numbers) else blank.get("blank_number")
                        options = blank.get("options", {})
                        correct_answer = blank.get("correct_answer")
                        correct_word = blank.get("correct_word")

                        if not blank_number or not options:
                            continue

                        # 调用 AI 分析考点（传入 db_session 支持课本释义查询）
                        analysis = await cloze_analyzer.analyze_point(
                            blank_number=blank_number,
                            correct_word=correct_word or "",
                            options=options,
                            context=normalized_content,
                            db_session=session  # 支持课本单词表查询
                        )

                        # 提取上下文句子
                        sentence = cloze_analyzer.extract_context(
                            normalized_content, blank_number
                        )

                        # 确定 legacy_point_type（向后兼容）
                        legacy_point_type = analysis.point_type if analysis.success and analysis.point_type else None

                        # 提取 primary_point_code（带调试日志）
                        primary_point_code = None
                        if analysis.success and analysis.primary_point:
                            primary_point_code = analysis.primary_point.get("code")
                            if primary_point_code:
                                print(f"    空{blank_number}: {correct_word} → {primary_point_code}")
                            else:
                                print(f"    ⚠ 空{blank_number}: primary_point.code 为空")
                        else:
                            if not analysis.success:
                                print(f"    ⚠ 空{blank_number}: 分析失败 - {analysis.error}")
                            else:
                                print(f"    ⚠ 空{blank_number}: primary_point 为 None")

                        # 创建考点记录（V2 格式）
                        cloze_point = ClozePoint(
                            cloze_id=cloze_passage.id,
                            blank_number=blank_number,
                            correct_answer=correct_answer,
                            correct_word=correct_word,
                            options=json.dumps(options, ensure_ascii=False),
                            # V2 考点分类
                            primary_point_code=primary_point_code,
                            legacy_point_type=legacy_point_type,
                            # 保留旧字段兼容
                            point_type=legacy_point_type,
                            translation=analysis.translation if analysis.success else None,
                            explanation=analysis.explanation if analysis.success else None,
                            confusion_words=json.dumps(analysis.confusion_words, ensure_ascii=False) if analysis.success and analysis.confusion_words else None,
                            sentence=sentence,
                            # 固定搭配专用字段
                            phrase=analysis.phrase if analysis.success else None,
                            similar_phrases=json.dumps(analysis.similar_phrases, ensure_ascii=False) if analysis.success and analysis.similar_phrases else None,
                            # 词义辨析专用字段
                            word_analysis=json.dumps(analysis.word_analysis, ensure_ascii=False) if analysis.success and analysis.word_analysis else None,
                            dictionary_source=analysis.dictionary_source if analysis.success else None,
                            # 熟词僻义专用字段
                            textbook_meaning=analysis.textbook_meaning if analysis.success else None,
                            textbook_source=analysis.textbook_source if analysis.success else None,
                            context_meaning=analysis.context_meaning if analysis.success else None,
                            similar_words=json.dumps(analysis.similar_words, ensure_ascii=False) if analysis.success and analysis.similar_words else None,
                            # 通用
                            tips=analysis.tips if analysis.success else None
                        )
                        session.add(cloze_point)
                        await session.flush()  # 获取 cloze_point.id

                        # 保存辅助考点（V5 字段重命名）
                        if analysis.success and analysis.secondary_points:
                            from app.models.cloze import ClozeSecondaryPoint
                            for idx, sp in enumerate(analysis.secondary_points):
                                # point_code 有 NOT NULL 约束，必须填充
                                code = sp.get("code") or sp.get("point_code") or "D1"
                                sec_point = ClozeSecondaryPoint(
                                    cloze_point_id=cloze_point.id,
                                    point_code=code,
                                    weight=sp.get("weight", "auxiliary"),
                                    explanation=sp.get("explanation"),
                                    sort_order=idx
                                )
                                session.add(sec_point)

                        # 保存排错点（V5 字段：rejection_code / rejection_reason）
                        if analysis.success and analysis.rejection_points:
                            from app.models.cloze import ClozeRejectionPoint
                            for rp in analysis.rejection_points:
                                code = rp.get("rejection_code") or rp.get("code") or "D1"
                                # 优先取 rejection_reason，fallback 到 explanation（与 cloze.py API 保持一致）
                                reason = rp.get("rejection_reason") or rp.get("explanation") or ""

                                # 验证日志：当 rejection_reason 为空时打印警告
                                if not reason:
                                    print(f"    ⚠ 排错点 {rp.get('option_word')} 缺少 rejection_reason")

                                rej_point = ClozeRejectionPoint(
                                    cloze_point_id=cloze_point.id,
                                    option_word=rp.get("option_word"),
                                    # point_code 有 NOT NULL 约束，必须填充
                                    point_code=code,
                                    rejection_code=code,
                                    explanation=reason,
                                    rejection_reason=reason
                                )
                                session.add(rej_point)
                        result["cloze_points"] += 1

                    print(f"  ✓ 完形填空: {len(blanks)} 个空格已分析")

            await session.commit()

    except Exception as e:
        result["status"] = "failed"
        result["error"] = str(e)

    result["time"] = time.time() - start_time
    return result


async def import_papers(
    papers_dir: Path,
    limit: Optional[int] = None,
    year_filter: Optional[int] = None,
    grade_filter: Optional[str] = None
) -> List[Dict]:
    """批量导入试卷"""
    results = []
    batch_id = datetime.now().strftime("%Y%m%d%H%M%S")

    # 查找所有docx文件
    docx_files = list(papers_dir.rglob("*.docx"))
    print(f"找到 {len(docx_files)} 个docx文件")

    # 应用筛选条件
    if year_filter:
        docx_files = [f for f in docx_files if str(year_filter) in f.name]
    if grade_filter:
        docx_files = [f for f in docx_files if grade_filter in f.name]

    # 限制数量
    if limit:
        docx_files = docx_files[:limit]

    print(f"将处理 {len(docx_files)} 个文件")

    # 导入进度
    success_count = 0
    failed_count = 0
    total_passages = 0

    for i, file_path in enumerate(docx_files, 1):
        print(f"\n[{i}/{len(docx_files)}] 处理: {file_path.name}")

        result = await import_paper(file_path, batch_id)
        results.append(result)

        if result["status"] == "completed":
            success_count += 1
            total_passages += result["passages"]
            print(f"  ✓ 成功 ({result['passages']}篇文章)")
        else:
            failed_count += 1
            print(f"  ✗ 失败: {result['error']}")

        # 打印进度
        if i % 10 == 0:
            print(f"\n--- 进度: {i}/{len(docx_files)}, 成功: {success_count}, 失败: {failed_count} ---")

    # 打印总结
    print("\n" + "=" * 50)
    print("导入完成!")
    print(f"总文件数: {len(docx_files)}")
    print(f"成功: {success_count}")
    print(f"失败: {failed_count}")
    print(f"总文章数: {total_passages}")
    print("=" * 50)

    return results


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="批量导入试卷")
    parser.add_argument(
        "--dir",
        type=str,
        default=None,
        help="试卷目录路径（默认使用配置中的RAW_PAPERS_DIR）"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="限制导入数量"
    )
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help="筛选年份"
    )
    parser.add_argument(
        "--grade",
        type=str,
        default=None,
        help="筛选年级（初一/初二/初三）"
    )

    args = parser.parse_args()

    # 确定试卷目录
    if args.dir:
        papers_dir = Path(args.dir)
    else:
        from app.config import settings
        papers_dir = settings.RAW_PAPERS_DIR

    if not papers_dir.exists():
        print(f"错误: 试卷目录不存在: {papers_dir}")
        sys.exit(1)

    print(f"试卷目录: {papers_dir}")
    print("=" * 50)

    await import_papers(
        papers_dir,
        limit=args.limit,
        year_filter=args.year,
        grade_filter=args.grade
    )


if __name__ == "__main__":
    asyncio.run(main())
