"""
试卷管理API
"""
import os
import json
import asyncio
import tempfile
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete

from app.database import get_db, async_session_factory
from app.models.paper import ExamPaper
from app.models.reading import ReadingPassage, Question
from app.models.vocabulary import Vocabulary, VocabularyPassage
from app.schemas.paper import PaperCreate, PaperResponse, PaperListResponse
from app.services.docx_parser import DocxParser
from app.services.llm_parser import LLMDocumentParser
from app.services.topic_classifier import TopicClassifier
from app.services.vocab_extractor import VocabExtractor

router = APIRouter()


# ============================================================================
#  辅助函数
# ============================================================================

async def get_or_create_vocabulary(db, word: str, lemma: str, frequency: int):
    """获取或创建词汇记录"""
    result = await db.execute(
        select(Vocabulary).where(Vocabulary.word == word)
    )
    vocab = result.scalar_one_or_none()

    if not vocab:
        vocab = Vocabulary(
            word=word,
            lemma=lemma,
            frequency=frequency
        )
        db.add(vocab)
        await db.flush()
    else:
        vocab.frequency = (vocab.frequency or 0) + frequency

    return vocab


# ============================================================================
#  普通上传接口 (保留兼容)
# ============================================================================

@router.post("/upload")
async def upload_paper(
    file: UploadFile = File(...),
    force: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """上传试卷 (使用AI解析)"""
    if not file.filename.endswith(".docx"):
        raise HTTPException(status_code=400, detail="只支持.docx格式")

    # 检查是否已存在
    result = await db.execute(
        select(ExamPaper).where(ExamPaper.filename == file.filename)
    )
    existing_paper = result.scalar_one_or_none()

    if existing_paper and not force:
        return {
            "status": "exists",
            "message": "试卷已存在",
            "paper_id": existing_paper.id
        }

    # 强制模式：删除旧记录
    if existing_paper:
        await db.execute(
            delete(ReadingPassage).where(ReadingPassage.paper_id == existing_paper.id)
        )
        await db.delete(existing_paper)
        await db.flush()

    # 保存临时文件
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # 解析文件名获取元数据
        filename_parser = DocxParser(file.filename)
        metadata = filename_parser.parse_filename()

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

        # 使用LLM解析
        llm_parser = LLMDocumentParser()

        try:
            # 上传文件到DashScope
            fileid = await llm_parser.upload_file(tmp_path)

            # AI解析
            llm_result = await llm_parser.parse_document_with_fileid(fileid)

            if llm_result.success:
                paper.import_status = "completed"
                paper.parse_strategy = "llm"
                paper.confidence = 0.95

                # 更新元数据
                if llm_result.metadata:
                    paper.year = llm_result.metadata.get("year", paper.year)
                    paper.region = llm_result.metadata.get("region", paper.region)
                    paper.grade = llm_result.metadata.get("grade", paper.grade)
                    paper.semester = llm_result.metadata.get("semester", paper.semester)
                    paper.exam_type = llm_result.metadata.get("exam_type", paper.exam_type)

                # 保存文章和题目
                saved_passages = []
                questions_created = 0

                for passage_data in llm_result.passages:
                    passage = ReadingPassage(
                        paper_id=paper.id,
                        passage_type=passage_data.get("passage_type", "C"),
                        content=passage_data.get("content", ""),
                        word_count=passage_data.get("word_count", 0)
                    )
                    db.add(passage)
                    await db.flush()
                    saved_passages.append(passage)

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

                # 话题分类
                try:
                    classifier = TopicClassifier()
                    for passage in saved_passages:
                        if passage.content and len(passage.content) > 50:
                            topic_result = await classifier.classify(passage.content, paper.grade)
                            if topic_result.success:
                                passage.primary_topic = topic_result.primary_topic
                                passage.secondary_topics = json.dumps(topic_result.secondary_topics or [], ensure_ascii=False)
                                passage.topic_confidence = topic_result.confidence
                                if topic_result.keywords:
                                    passage.keywords = json.dumps(topic_result.keywords, ensure_ascii=False)
                except Exception:
                    pass

                # 词汇提取
                try:
                    vocab_extractor = VocabExtractor(min_length=3, min_frequency=1)
                    for passage in saved_passages:
                        if passage.content and len(passage.content) > 20:
                            extracted_words = vocab_extractor.extract(passage.content)
                            for word_data in extracted_words:
                                vocab = await get_or_create_vocabulary(
                                    db, word_data.word, word_data.lemma, word_data.frequency
                                )
                                for occ in word_data.occurrences:
                                    vocab_passage = VocabularyPassage(
                                        vocabulary_id=vocab.id,
                                        passage_id=passage.id,
                                        sentence=occ.sentence,
                                        char_position=occ.char_position,
                                        end_position=occ.end_position,
                                        word_position=occ.word_position
                                    )
                                    db.add(vocab_passage)
                except Exception:
                    pass

                await db.commit()

                return {
                    "status": "success",
                    "paper_id": paper.id,
                    "passages_created": len(saved_passages),
                    "questions_created": questions_created,
                    "parse_strategy": "llm"
                }
            else:
                paper.import_status = "failed"
                paper.error_message = f"AI解析失败: {llm_result.error}"
                await db.commit()
                raise HTTPException(status_code=500, detail=f"AI解析失败: {llm_result.error}")

        except Exception as e:
            paper.import_status = "failed"
            paper.error_message = f"AI服务错误: {str(e)}"
            await db.commit()
            raise HTTPException(status_code=500, detail=f"AI服务错误: {str(e)}")

    finally:
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
        try:
            result = await upload_paper(file, db=db)
            results.append(result)
        except HTTPException as e:
            results.append({
                "status": "error",
                "filename": file.filename,
                "error": e.detail
            })
        except Exception as e:
            results.append({
                "status": "error",
                "filename": file.filename,
                "error": str(e)
            })

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


# ============================================================================
#  SSE 进度推送接口 (完全依赖AI，无规则回退)
# ============================================================================

@router.post("/upload-with-progress")
async def upload_paper_with_progress(
    file: UploadFile = File(...),
    force: bool = False,
):
    """
    上传试卷并实时返回处理进度 (SSE)

    完全依赖AI模型解析，无规则回退

    进度阶段:
    - uploading: 上传文件中
    - uploaded: 文件上传完成
    - parsing_filename: 解析文件名
    - parsed_filename: 文件名解析完成
    - uploading_to_ai: 上传到AI服务
    - uploaded_to_ai: AI服务就绪
    - ai_parsing: AI解析文档中 (最耗时)
    - ai_parsed: AI解析完成
    - topic_classifying: AI话题分类中
    - topic_classified: 话题分类完成
    - vocab_extracting: 词汇提取中
    - vocab_extracted: 词汇提取完成
    - completed: 完成
    - error: 发生错误
    """

    async def event_generator():
        tmp_path = None
        saved_passages = []

        try:
            # Step 1: 保存临时文件
            yield f"data: {json.dumps({'stage': 'uploading', 'message': '上传文件中...', 'progress': 10}, ensure_ascii=False)}\n\n"

            if not file.filename.endswith(".docx"):
                yield f"data: {json.dumps({'stage': 'error', 'message': '只支持docx格式', 'progress': 0}, ensure_ascii=False)}\n\n"
                return

            with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
                content = await file.read()
                tmp.write(content)
                tmp_path = tmp.name

            yield f"data: {json.dumps({'stage': 'uploaded', 'message': '文件上传完成', 'progress': 15}, ensure_ascii=False)}\n\n"

            # Step 2: 解析文件名
            yield f"data: {json.dumps({'stage': 'parsing_filename', 'message': '解析文件名...', 'progress': 20}, ensure_ascii=False)}\n\n"

            filename_parser = DocxParser(file.filename)
            metadata = filename_parser.parse_filename()

            grade_info = f"{metadata.get('grade', '')} {metadata.get('exam_type', '')}".strip()
            yield f"data: {json.dumps({'stage': 'parsed_filename', 'message': f'识别: {grade_info}', 'progress': 25, 'metadata': metadata}, ensure_ascii=False)}\n\n"

            # 创建独立的数据库会话
            async with async_session_factory() as db:
                # 检查是否已存在
                result = await db.execute(
                    select(ExamPaper).where(ExamPaper.filename == file.filename)
                )
                existing_paper = result.scalar_one_or_none()

                if existing_paper:
                    if not force:
                        yield f"data: {json.dumps({'stage': 'completed', 'message': '试卷已存在', 'progress': 100, 'result': {'status': 'exists', 'paper_id': existing_paper.id}}, ensure_ascii=False)}\n\n"
                        return
                    # 强制模式：删除旧记录
                    await db.execute(
                        delete(ReadingPassage).where(ReadingPassage.paper_id == existing_paper.id)
                    )
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

                # Step 3: 上传到AI服务
                yield f"data: {json.dumps({'stage': 'uploading_to_ai', 'message': '上传到AI服务...', 'progress': 30}, ensure_ascii=False)}\n\n"

                llm_parser = LLMDocumentParser()

                # 上传文件到DashScope
                fileid = await llm_parser.upload_file(tmp_path)
                yield f"data: {json.dumps({'stage': 'uploaded_to_ai', 'message': 'AI服务已就绪', 'progress': 35}, ensure_ascii=False)}\n\n"

                # Step 4: AI解析
                yield f"data: {json.dumps({'stage': 'ai_parsing', 'message': '🤖 AI正在解析文档...', 'progress': 40}, ensure_ascii=False)}\n\n"

                llm_result = await llm_parser.parse_document_with_fileid(fileid)

                yield f"data: {json.dumps({'stage': 'ai_parsed', 'message': 'AI解析完成', 'progress': 60}, ensure_ascii=False)}\n\n"

                if not llm_result.success:
                    paper.import_status = "failed"
                    paper.error_message = f"AI解析失败: {llm_result.error}"
                    await db.commit()
                    yield f"data: {json.dumps({'stage': 'error', 'message': f'AI解析失败: {llm_result.error}', 'progress': 0}, ensure_ascii=False)}\n\n"
                    return

                paper.import_status = "completed"
                paper.parse_strategy = "llm"
                paper.confidence = 0.95

                # 更新元数据
                if llm_result.metadata:
                    paper.year = llm_result.metadata.get("year", paper.year)
                    paper.region = llm_result.metadata.get("region", paper.region)
                    paper.grade = llm_result.metadata.get("grade", paper.grade)
                    paper.semester = llm_result.metadata.get("semester", paper.semester)
                    paper.exam_type = llm_result.metadata.get("exam_type", paper.exam_type)
                    metadata.update(llm_result.metadata)

                # Step 5: 保存文章和题目
                yield f"data: {json.dumps({'stage': 'saving', 'message': '保存数据中...', 'progress': 65}, ensure_ascii=False)}\n\n"

                for passage_data in llm_result.passages:
                    passage = ReadingPassage(
                        paper_id=paper.id,
                        passage_type=passage_data.get("passage_type", "C"),
                        content=passage_data.get("content", ""),
                        word_count=passage_data.get("word_count", 0)
                    )
                    db.add(passage)
                    await db.flush()
                    passages_created += 1
                    saved_passages.append(passage)

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

                # Step 6: AI话题分类
                yield f"data: {json.dumps({'stage': 'topic_classifying', 'message': '🎯 AI正在提炼主题...', 'progress': 75}, ensure_ascii=False)}\n\n"

                try:
                    classifier = TopicClassifier()
                    for passage in saved_passages:
                        if passage.content and len(passage.content) > 50:
                            topic_result = await classifier.classify(passage.content, paper.grade)
                            if topic_result.success:
                                passage.primary_topic = topic_result.primary_topic
                                passage.secondary_topics = json.dumps(topic_result.secondary_topics or [], ensure_ascii=False)
                                passage.topic_confidence = topic_result.confidence
                                if topic_result.keywords:
                                    passage.keywords = json.dumps(topic_result.keywords, ensure_ascii=False)

                    yield f"data: {json.dumps({'stage': 'topic_classified', 'message': '主题分类完成', 'progress': 82}, ensure_ascii=False)}\n\n"
                except Exception as e:
                    yield f"data: {json.dumps({'stage': 'topic_classified', 'message': f'主题分类跳过: {str(e)}', 'progress': 82}, ensure_ascii=False)}\n\n"

                # Step 7: 词汇提取
                yield f"data: {json.dumps({'stage': 'vocab_extracting', 'message': '📚 提取高频词汇...', 'progress': 85}, ensure_ascii=False)}\n\n"

                try:
                    vocab_extractor = VocabExtractor(min_length=3, min_frequency=1)
                    for passage in saved_passages:
                        if passage.content and len(passage.content) > 20:
                            extracted_words = vocab_extractor.extract(passage.content)

                            for word_data in extracted_words:
                                vocab = await get_or_create_vocabulary(
                                    db, word_data.word, word_data.lemma, word_data.frequency
                                )

                                for occ in word_data.occurrences:
                                    vocab_passage = VocabularyPassage(
                                        vocabulary_id=vocab.id,
                                        passage_id=passage.id,
                                        sentence=occ.sentence,
                                        char_position=occ.char_position,
                                        end_position=occ.end_position,
                                        word_position=occ.word_position
                                    )
                                    db.add(vocab_passage)

                    yield f"data: {json.dumps({'stage': 'vocab_extracted', 'message': '词汇提取完成', 'progress': 95}, ensure_ascii=False)}\n\n"
                except Exception as e:
                    yield f"data: {json.dumps({'stage': 'vocab_extracted', 'message': f'词汇提取跳过: {str(e)}', 'progress': 95}, ensure_ascii=False)}\n\n"

                await db.commit()

                result_data = {
                    "status": "success",
                    "filename": file.filename,
                    "paper_id": paper.id,
                    "passages_created": passages_created,
                    "questions_created": questions_created,
                    "metadata": metadata,
                    "parse_strategy": "llm",
                    "confidence": 0.95
                }

                yield f"data: {json.dumps({'stage': 'completed', 'message': '✅ 导入完成', 'progress': 100, 'result': result_data}, ensure_ascii=False)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'stage': 'error', 'message': f'❌ 错误: {str(e)}', 'progress': 0}, ensure_ascii=False)}\n\n"

        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# ============================================================================
#  试卷管理接口
# ============================================================================

@router.get("/", response_model=PaperListResponse)
async def list_papers(
    page: int = 1,
    size: int = 20,
    year: Optional[int] = None,
    region: Optional[str] = None,
    grade: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """获取试卷列表"""
    query = select(ExamPaper)

    if year:
        query = query.where(ExamPaper.year == year)
    if region:
        query = query.where(ExamPaper.region == region)
    if grade:
        query = query.where(ExamPaper.grade == grade)

    # 获取总数
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # 分页
    query = query.offset((page - 1) * size).limit(size)
    query = query.order_by(ExamPaper.created_at.desc())

    result = await db.execute(query)
    papers = result.scalars().all()

    return {
        "total": total,
        "items": papers
    }


@router.get("/{paper_id}", response_model=PaperResponse)
async def get_paper(
    paper_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取试卷详情"""
    result = await db.execute(
        select(ExamPaper).where(ExamPaper.id == paper_id)
    )
    paper = result.scalar_one_or_none()

    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在")

    return paper


@router.delete("/{paper_id}")
async def delete_paper(
    paper_id: int,
    db: AsyncSession = Depends(get_db)
):
    """删除试卷"""
    result = await db.execute(
        select(ExamPaper).where(ExamPaper.id == paper_id)
    )
    paper = result.scalar_one_or_none()

    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在")

    # 删除关联的文章
    await db.execute(
        delete(ReadingPassage).where(ReadingPassage.paper_id == paper_id)
    )

    await db.delete(paper)
    await db.commit()

    return {"message": "删除成功"}
