#!/usr/bin/env python
"""
试卷批量导入脚本

遍历试卷目录，解析并导入数据库
"""
import asyncio
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
from app.services.docx_parser import DocxParser, ParseStrategy


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
        year=metadata.get("year", 0),
        region=metadata.get("region"),
        school=metadata.get("school"),
        grade=metadata.get("grade", ""),
        semester=metadata.get("semester"),
        season=metadata.get("season"),
        exam_type=metadata.get("exam_type"),
        version=metadata.get("version", "学生版"),
        import_status="pending"
    )
    session.add(paper)
    await session.flush()

    return paper


async def import_paper(file_path: Path, batch_id: str) -> Dict:
    """导入单个试卷"""
    start_time = time.time()
    result = {
        "filename": file_path.name,
        "status": "pending",
        "error": None,
        "passages": 0
    }

    try:
        # 初始化解析器
        parser = DocxParser(str(file_path))

        # 解析文件名获取元数据
        metadata = parser.parse_filename()

        # 从文件路径提取目录结构信息（如果有）
        # 目录格式: {年份}/{年级}{学期类型}/{区县}/
        parent_dir = file_path.parent
        if parent_dir.name in ["东城", "西城", "海淀", "朝阳", "丰台", "石景山",
                               "通州", "顺义", "昌平", "大兴", "房山", "门头沟",
                               "怀柔", "平谷", "密云", "延庆"]:
            metadata["region"] = parent_dir.name

        # 加载文档
        if not parser.load():
            result["status"] = "failed"
            result["error"] = "无法加载文档"
            return result

        async with async_session() as session:
            # 创建试卷记录
            paper = await get_or_create_paper(session, file_path.name, file_path, metadata)

            # 提取阅读C/D篇
            parse_result = parser.extract_reading_passages()

            if parse_result.success:
                paper.import_status = "completed"
                paper.parse_strategy = parse_result.strategy.value
                paper.confidence = parse_result.confidence

                # 保存C篇
                if parse_result.data and "c_passage" in parse_result.data:
                    c_data = parse_result.data["c_passage"]
                    content = c_data.content if hasattr(c_data, 'content') else c_data["content"]
                    c_passage = ReadingPassage(
                        paper_id=paper.id,
                        passage_type="C",
                        content=content,
                        word_count=len(content.split())
                    )
                    session.add(c_passage)
                    result["passages"] += 1

                # 保存D篇
                if parse_result.data and "d_passage" in parse_result.data:
                    d_data = parse_result.data["d_passage"]
                    content = d_data.content if hasattr(d_data, 'content') else d_data["content"]
                    d_passage = ReadingPassage(
                        paper_id=paper.id,
                        passage_type="D",
                        content=content,
                        word_count=len(content.split())
                    )
                    session.add(d_passage)
                    result["passages"] += 1

                result["status"] = "completed"

            else:
                paper.import_status = "failed"
                paper.error_message = parse_result.error
                result["status"] = "failed"
                result["error"] = parse_result.error

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
