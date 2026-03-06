"""
试卷管理API
"""
import os
import tempfile
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete

from app.database import get_db
from app.models.paper import ExamPaper
from app.models.reading import ReadingPassage, Question
from app.schemas.paper import PaperCreate, PaperResponse, PaperListResponse
from app.services.docx_parser import DocxParser
from app.services.llm_parser import LLMDocumentParser

router = APIRouter()


@router.get("", response_model=PaperListResponse)
async def list_papers(
    year: Optional[int] = None,
    grade: Optional[str] = None,
    region: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    size: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """获取试卷列表"""
    query = select(ExamPaper)

    # 筛选条件
    if year:
        query = query.where(ExamPaper.year == year)
    if grade:
        query = query.where(ExamPaper.grade == grade)
    if region:
        query = query.where(ExamPaper.region == region)
    if status:
        query = query.where(ExamPaper.import_status == status)

    # 统计总数
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)

    # 分页
    query = query.offset((page - 1) * size).limit(size)
    query = query.order_by(ExamPaper.created_at.desc())

    result = await db.execute(query)
    papers = result.scalars().all()

    return PaperListResponse(
        total=total or 0,
        items=[PaperResponse.model_validate(p) for p in papers]
    )


@router.get("/{paper_id}", response_model=PaperResponse)
async def get_paper(
    paper_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取单个试卷详情"""
    query = select(ExamPaper).where(ExamPaper.id == paper_id)
    result = await db.execute(query)
    paper = result.scalar_one_or_none()

    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在")

    return PaperResponse.model_validate(paper)


@router.post("/upload")
async def upload_paper(
    file: UploadFile = File(...),
    force: bool = False,  # 强制重新导入
    use_llm: bool = True,  # 使用LLM解析（更准确）
    db: AsyncSession = Depends(get_db)
):
    """上传并解析单个试卷

    Args:
        file: 上传的docx文件
        force: 是否强制重新导入（即使试卷已存在）
        use_llm: 是否使用LLM解析（默认True，更准确但有成本）
    """
    if not file.filename.endswith(".docx"):
        raise HTTPException(status_code=400, detail="只支持docx格式")

    # 保存临时文件
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # 先从原始文件名解析元数据（使用DocxParser的静态方法或直接解析）
        from pathlib import Path
        original_filename = file.filename

        # 使用原始文件名解析元数据
        filename_parser = DocxParser(original_filename)  # 用文件名创建parser
        metadata = filename_parser.parse_filename()  # 解析文件名获取元数据

        # 使用临时文件路径创建实际解析内容的parser
        parser = DocxParser(tmp_path)

        # 加载文档
        if not parser.load():
            return {
                "status": "failed",
                "filename": file.filename,
                "error": "无法加载文档"
            }

        # 检查是否已存在
        result = await db.execute(
            select(ExamPaper).where(ExamPaper.filename == file.filename)
        )
        existing_paper = result.scalar_one_or_none()

        if existing_paper:
            if not force:
                return {
                    "status": "exists",
                    "filename": file.filename,
                    "paper_id": existing_paper.id,
                    "message": "试卷已存在，如需重新导入请使用强制导入"
                }
            # 强制模式：删除旧记录及其关联的文章
            # 先删除关联的文章
            await db.execute(
                delete(ReadingPassage).where(ReadingPassage.paper_id == existing_paper.id)
            )
            # 再删除试卷
            await db.delete(existing_paper)
            await db.flush()

        # 创建试卷记录
        paper = ExamPaper(
            filename=file.filename,
            original_path=tmp_path,
            year=metadata.get("year", 0),
            region=metadata.get("region"),
            grade=metadata.get("grade", ""),
            semester=metadata.get("semester"),
            exam_type=metadata.get("exam_type"),
            version=metadata.get("version", "学生版"),
            import_status="processing"
        )
        db.add(paper)
        await db.flush()

        passages_created = 0
        questions_created = 0
        parse_strategy = "rule"
        confidence = 0.0

        # 选择解析方式
        if use_llm:
            # 使用LLM解析（更准确）
            llm_parser = LLMDocumentParser()
            llm_result = await llm_parser.parse_document(tmp_path, use_fileid=False)

            if llm_result.success:
                parse_strategy = "llm"
                confidence = 0.95
                paper.import_status = "completed"
                paper.parse_strategy = parse_strategy
                paper.confidence = confidence

                # 更新元数据
                if llm_result.metadata:
                    paper.year = llm_result.metadata.get("year", paper.year)
                    paper.region = llm_result.metadata.get("region", paper.region)
                    paper.grade = llm_result.metadata.get("grade", paper.grade)
                    paper.semester = llm_result.metadata.get("semester", paper.semester)
                    paper.exam_type = llm_result.metadata.get("exam_type", paper.exam_type)
                    metadata.update(llm_result.metadata)

                # 保存文章
                for passage_data in llm_result.passages:
                    passage = ReadingPassage(
                        paper_id=paper.id,
                        passage_type=passage_data.get("passage_type", "C"),
                        content=passage_data.get("content", ""),
                        word_count=passage_data.get("word_count", 0)
                    )
                    db.add(passage)
                    await db.flush()  # 获取passage.id
                    passages_created += 1

                    # 保存题目
                    questions_data = passage_data.get("questions", [])
                    if questions_data:
                        passage.has_questions = True
                        for q_data in questions_data:
                            options = q_data.get("options", {})
                            question = Question(
                                passage_id=passage.id,
                                question_number=q_data.get("question_number"),
                                question_text=q_data.get("question_text", ""),
                                option_a=options.get("A"),
                                option_b=options.get("B"),
                                option_c=options.get("C"),
                                option_d=options.get("D"),
                                correct_answer=q_data.get("correct_answer"),
                                answer_explanation=q_data.get("answer_explanation")
                            )
                            db.add(question)
                            questions_created += 1

                await db.commit()

                return {
                    "status": "success",
                    "filename": file.filename,
                    "paper_id": paper.id,
                    "passages_created": passages_created,
                    "questions_created": questions_created,
                    "metadata": metadata,
                    "parse_strategy": parse_strategy,
                    "confidence": confidence
                }
            else:
                # LLM解析失败，回退到规则解析
                paper.error_message = f"LLM解析失败: {llm_result.error}，回退到规则解析"

        # 使用规则解析（默认或LLM失败回退）
        parse_result = parser.extract_reading_passages()

        if parse_result.success:
            paper.import_status = "completed"
            parse_strategy = parse_result.strategy.value
            confidence = parse_result.confidence
            paper.parse_strategy = parse_strategy
            paper.confidence = confidence

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
                db.add(c_passage)
                passages_created += 1

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
                db.add(d_passage)
                passages_created += 1

            await db.commit()

            return {
                "status": "success",
                "filename": file.filename,
                "paper_id": paper.id,
                "passages_created": passages_created,
                "questions_created": questions_created,
                "metadata": metadata,
                "parse_strategy": parse_strategy,
                "confidence": confidence
            }
        else:
            paper.import_status = "failed"
            paper.error_message = parse_result.error
            await db.commit()

            return {
                "status": "failed",
                "filename": file.filename,
                "error": parse_result.error,
                "metadata": metadata
            }

    except Exception as e:
        return {
            "status": "error",
            "filename": file.filename,
            "error": str(e)
        }
    finally:
        # 清理临时文件
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.post("/batch-upload")
async def batch_upload_papers(
    files: List[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db)
):
    """批量上传试卷"""
    results = []

    for file in files:
        result = await upload_paper(file, db)
        results.append(result)
        # 每个文件处理后重新获取db session
        db = Depends(get_db)()

    success_count = sum(1 for r in results if r.get("status") == "success")
    failed_count = sum(1 for r in results if r.get("status") in ["failed", "error"])
    exists_count = sum(1 for r in results if r.get("status") == "exists")

    return {
        "total": len(files),
        "success": success_count,
        "failed": failed_count,
        "exists": exists_count,
        "results": results
    }
