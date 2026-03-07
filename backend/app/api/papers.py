"""
试卷管理API

可扩展的步骤化处理流程
"""
import os
import re
import json
import asyncio
import tempfile
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from sqlalchemy.orm import selectinload

from app.database import get_db, async_session_factory


def count_english_words(text: str) -> int:
    """精确计算英文词数（只匹配英文字母组成的单词）"""
    if not text:
        return 0
    # 匹配连续的英文字母（包括带连字符的单词）
    words = re.findall(r"[a-zA-Z]+(?:-[a-zA-Z]+)*", text)
    return len(words)
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
#  步骤定义 - 可扩展配置
# ============================================================================

class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PipelineStep:
    """处理步骤"""
    id: str
    name: str
    description: str
    icon: str = "⚙️"
    status: StepStatus = StepStatus.PENDING
    progress: int = 0
    message: str = ""
    error: str = ""
    data: Dict[str, Any] = field(default_factory=dict)


# 步骤配置 - 未来扩展只需添加新步骤
PIPELINE_CONFIG = [
    {"id": "upload", "name": "上传文件", "description": "上传试卷文件到服务器", "icon": "📤"},
    {"id": "parse_filename", "name": "解析文件名", "description": "从文件名提取元数据", "icon": "📝"},
    {"id": "upload_to_ai", "name": "上传AI服务", "description": "上传文件到通义千问", "icon": "☁️"},
    {"id": "ai_parse", "name": "AI解析文档", "description": "提取C/D篇阅读和题目", "icon": "🤖"},
    {"id": "save_passages", "name": "保存文章", "description": "保存阅读文章到数据库", "icon": "💾"},
    {"id": "save_questions", "name": "保存题目", "description": "保存阅读题目到数据库", "icon": "❓"},
    {"id": "topic_classify", "name": "AI话题分类", "description": "提炼文章主题", "icon": "🎯"},
    {"id": "vocab_extract", "name": "词汇提取", "description": "提取高频词汇", "icon": "📚"},
]


class ProgressReporter:
    """进度报告器 - 管理所有步骤状态"""

    def __init__(self):
        self.steps: Dict[str, PipelineStep] = {}
        for config in PIPELINE_CONFIG:
            self.steps[config["id"]] = PipelineStep(**config)

    def start_step(self, step_id: str, message: str = ""):
        """开始一个步骤"""
        if step_id in self.steps:
            self.steps[step_id].status = StepStatus.RUNNING
            self.steps[step_id].message = message
            self.steps[step_id].progress = 0

    def update_step(self, step_id: str, progress: int = None, message: str = None):
        """更新步骤进度"""
        if step_id in self.steps:
            if progress is not None:
                self.steps[step_id].progress = progress
            if message is not None:
                self.steps[step_id].message = message

    def complete_step(self, step_id: str, message: str = "", data: Dict = None):
        """完成一个步骤"""
        if step_id in self.steps:
            self.steps[step_id].status = StepStatus.COMPLETED
            self.steps[step_id].progress = 100
            self.steps[step_id].message = message
            if data:
                self.steps[step_id].data = data

    def fail_step(self, step_id: str, error: str):
        """步骤失败"""
        if step_id in self.steps:
            self.steps[step_id].status = StepStatus.FAILED
            self.steps[step_id].error = error

    def skip_step(self, step_id: str, reason: str = ""):
        """跳过步骤"""
        if step_id in self.steps:
            self.steps[step_id].status = StepStatus.SKIPPED
            self.steps[step_id].message = reason

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "type": "step_update",
            "steps": [
                {
                    "id": step.id,
                    "name": step.name,
                    "description": step.description,
                    "icon": step.icon,
                    "status": step.status.value,
                    "progress": step.progress,
                    "message": step.message,
                    "error": step.error,
                }
                for step in self.steps.values()
            ],
            "current_step": self._get_current_step(),
            "overall_progress": self._calculate_overall_progress(),
        }

    def _get_current_step(self) -> Optional[str]:
        """获取当前运行的步骤"""
        for step in self.steps.values():
            if step.status == StepStatus.RUNNING:
                return step.id
        return None

    def _calculate_overall_progress(self) -> int:
        """计算总体进度"""
        total = len(self.steps)
        completed = sum(1 for s in self.steps.values() if s.status == StepStatus.COMPLETED)
        running_progress = sum(s.progress for s in self.steps.values() if s.status == StepStatus.RUNNING)
        return int((completed * 100 + running_progress) / total)


# ============================================================================
#  SSE 进度推送接口
# ============================================================================

@router.post("/upload-with-progress")
async def upload_paper_with_progress(
    file: UploadFile = File(...),
    force: bool = False,
):
    """
    上传试卷并实时返回处理进度 (SSE)

    可扩展的步骤化处理流程， 每个步骤独立展示
    """

    async def event_generator():
        reporter = ProgressReporter()
        tmp_path = None
        saved_passages = []
        metadata = {}

        def emit():
            """发送进度事件"""
            return f"data: {json.dumps(reporter.to_dict(), ensure_ascii=False)}\n\n"

        try:
            # ===== Step 1: 上传文件 =====
            reporter.start_step("upload", "正在上传文件...")
            yield emit()

            if not file.filename.endswith(".docx"):
                reporter.fail_step("upload", "只支持.docx格式")
                yield emit()
                return

            with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
                content = await file.read()
                tmp.write(content)
                tmp_path = tmp.name

            reporter.complete_step("upload", f"文件大小: {len(content)/1024:.1f}KB")
            yield emit()

            # ===== Step 2: 解析文件名 =====
            reporter.start_step("parse_filename", "正在解析文件名...")
            yield emit()

            filename_parser = DocxParser(file.filename)
            metadata = filename_parser.parse_filename()
            grade_info = f"{metadata.get('grade', '')} {metadata.get('exam_type', '')}".strip()

            reporter.complete_step("parse_filename", f"识别: {grade_info}", data=metadata)
            yield emit()

            # 创建数据库会话
            async with async_session_factory() as db:
                # 检查是否已存在
                result = await db.execute(
                    select(ExamPaper).where(ExamPaper.filename == file.filename)
                )
                existing_paper = result.scalar_one_or_none()

                if existing_paper:
                    if not force:
                        reporter.complete_step("parse_filename", "试卷已存在")
                        yield emit()
                        # 跳过后续步骤
                        for step_id in ["upload_to_ai", "ai_parse", "save_passages",
                                       "save_questions", "topic_classify", "vocab_extract"]:
                            reporter.skip_step(step_id, "试卷已存在")
                        yield emit()
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

                # ===== Step 3: 上传到AI服务 =====
                reporter.start_step("upload_to_ai", "正在上传到通义千问...")
                yield emit()

                llm_parser = LLMDocumentParser()

                try:
                    fileid = await llm_parser.upload_file(tmp_path)
                    reporter.complete_step("upload_to_ai", "AI服务已就绪")
                    yield emit()
                except Exception as e:
                    reporter.fail_step("upload_to_ai", str(e))
                    yield emit()
                    return

                # ===== Step 4: AI解析文档 =====
                reporter.start_step("ai_parse", "🤖 AI正在解析文档...")
                yield emit()

                try:
                    # 更新进度消息
                    reporter.update_step("ai_parse", message="提取试卷结构...", progress=20)
                    yield emit()

                    llm_result = await llm_parser.parse_document_with_fileid(fileid)

                    if not llm_result.success:
                        reporter.fail_step("ai_parse", llm_result.error or "解析失败")
                        yield emit()
                        return

                    passages_count = len(llm_result.passages)
                    questions_count = sum(len(p.get("questions", [])) for p in llm_result.passages)

                    reporter.complete_step(
                        "ai_parse",
                        f"提取{passages_count}篇文章, {questions_count}道题目",
                        data={"passages": passages_count, "questions": questions_count}
                    )
                    yield emit()

                except Exception as e:
                    reporter.fail_step("ai_parse", str(e))
                    yield emit()
                    return

                # 更新试卷状态和元数据
                paper.import_status = "completed"
                paper.parse_strategy = "llm"
                paper.confidence = 0.95
                if llm_result.metadata:
                    paper.year = llm_result.metadata.get("year", paper.year)
                    paper.region = llm_result.metadata.get("region", paper.region)
                    paper.grade = llm_result.metadata.get("grade", paper.grade)
                    paper.semester = llm_result.metadata.get("semester", paper.semester)
                    paper.exam_type = llm_result.metadata.get("exam_type", paper.exam_type)
                    metadata.update(llm_result.metadata)

                # ===== Step 5: 保存文章 =====
                reporter.start_step("save_passages", "正在保存文章...")
                yield emit()

                passages_created = 0
                for i, passage_data in enumerate(llm_result.passages):
                    reporter.update_step("save_passages",
                        progress=int((i + 1) / len(llm_result.passages) * 100),
                        message=f"保存{passage_data.get('passage_type', 'C')}篇...")
                    yield emit()

                    passage = ReadingPassage(
                        paper_id=paper.id,
                        passage_type=passage_data.get("passage_type", "C"),
                        title=passage_data.get("title"),
                        content=passage_data.get("content", ""),
                        word_count=count_english_words(passage_data.get("content", ""))
                    )
                    db.add(passage)
                    await db.flush()
                    passages_created += 1
                    saved_passages.append(passage)

                reporter.complete_step("save_passages", f"已保存{passages_created}篇文章")
                yield emit()

                # ===== Step 6: 保存题目 =====
                reporter.start_step("save_questions", "正在保存题目...")
                yield emit()

                questions_created = 0
                for passage in saved_passages:
                    # 找到对应的解析数据
                    passage_data = next(
                        (p for p in llm_result.passages if p.get("passage_type") == passage.passage_type),
                        {}
                    )
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

                reporter.complete_step("save_questions", f"已保存{questions_created}道题目")
                yield emit()

                # ===== Step 7: AI话题分类 =====
                reporter.start_step("topic_classify", "🎯 AI正在提炼主题...")
                yield emit()

                try:
                    classifier = TopicClassifier()
                    topics_found = []

                    for i, passage in enumerate(saved_passages):
                        if passage.content and len(passage.content) > 50:
                            reporter.update_step("topic_classify",
                                progress=int((i + 1) / len(saved_passages) * 100),
                                message=f"分析{passage.passage_type}篇主题...")
                            yield emit()

                            topic_result = await classifier.classify(passage.content, paper.grade)
                            if topic_result.success:
                                passage.primary_topic = topic_result.primary_topic
                                passage.secondary_topics = json.dumps(
                                    topic_result.secondary_topics or [], ensure_ascii=False
                                )
                                passage.topic_confidence = topic_result.confidence
                                if topic_result.keywords:
                                    passage.keywords = json.dumps(topic_result.keywords, ensure_ascii=False)
                                topics_found.append(topic_result.primary_topic)

                    reporter.complete_step("topic_classify", f"已分类{len(topics_found)}篇文章主题")
                    yield emit()

                except Exception as e:
                    reporter.skip_step("topic_classify", f"跳过: {str(e)}")
                    yield emit()

                # ===== Step 8: AI词汇提取 =====
                reporter.start_step("vocab_extract", "📚 AI正在分析文章提取核心词汇...")
                yield emit()

                try:
                    vocab_extractor = VocabExtractor()
                    total_words = 0

                    for i, passage in enumerate(saved_passages):
                        if passage.content and len(passage.content) > 50:
                            reporter.update_step("vocab_extract",
                                progress=int((i + 1) / len(saved_passages) * 100),
                                message=f"AI分析{passage.passage_type}篇核心词汇...")
                            yield emit()

                            # 使用AI异步提取
                            extracted_words = await vocab_extractor.extract_async(passage.content)

                            for word_data in extracted_words:
                                # 查找或创建词汇记录
                                result = await db.execute(
                                    select(Vocabulary).where(Vocabulary.word == word_data.word)
                                )
                                vocab = result.scalar_one_or_none()

                                if not vocab:
                                    vocab = Vocabulary(
                                        word=word_data.word,
                                        lemma=word_data.lemma,
                                        frequency=0,  # 初始为0,由实际关联记录数决定
                                        definition=word_data.definition  # 保存AI释义
                                    )
                                    db.add(vocab)
                                    await db.flush()
                                else:
                                    # 不再累加 frequency,由数据库统计计算
                                    # 如果原来没有释义,更新AI释义
                                    if not vocab.definition and word_data.definition:
                                        vocab.definition = word_data.definition

                                # 创建关联记录（带去重检查）
                                for occ in word_data.occurrences:
                                    # 检查是否已存在相同的记录
                                    existing = await db.execute(
                                        select(VocabularyPassage).where(
                                            VocabularyPassage.vocabulary_id == vocab.id,
                                            VocabularyPassage.passage_id == passage.id,
                                            VocabularyPassage.char_position == occ.char_position
                                        )
                                    )
                                    if existing.scalar_one_or_none():
                                        continue  # 跳过重复记录

                                    vocab_passage = VocabularyPassage(
                                        vocabulary_id=vocab.id,
                                        passage_id=passage.id,
                                        sentence=occ.sentence,
                                        char_position=occ.char_position,
                                        end_position=occ.end_position,
                                        word_position=occ.word_position
                                    )
                                    db.add(vocab_passage)
                                    total_words += 1

                    reporter.complete_step("vocab_extract", f"AI已提取{total_words}个核心词汇")
                    yield emit()

                except Exception as e:
                    reporter.skip_step("vocab_extract", f"跳过: {str(e)}")
                    yield emit()

                # 提交所有更改
                await db.commit()

                # 发送最终结果
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

                # 添加最终结果到事件
                final_event = reporter.to_dict()
                final_event["type"] = "completed"
                final_event["result"] = result_data
                yield f"data: {json.dumps(final_event, ensure_ascii=False)}\n\n"

        except Exception as e:
            # 标记当前步骤为失败
            current = reporter._get_current_step()
            if current:
                reporter.fail_step(current, str(e))
            yield emit()

        finally:
            # 清理临时文件
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
#  其他接口
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

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    query = query.offset((page - 1) * size).limit(size)
    query = query.order_by(ExamPaper.created_at.desc())

    result = await db.execute(query)
    papers = result.scalars().all()

    return {"total": total, "items": papers}


@router.get("/{paper_id}", response_model=PaperResponse)
async def get_paper(paper_id: int, db: AsyncSession = Depends(get_db)):
    """获取试卷详情"""
    result = await db.execute(
        select(ExamPaper).where(ExamPaper.id == paper_id)
    )
    paper = result.scalar_one_or_none()

    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在")

    return paper


@router.delete("/{paper_id}")
async def delete_paper(paper_id: int, db: AsyncSession = Depends(get_db)):
    """删除试卷"""
    result = await db.execute(
        select(ExamPaper).where(ExamPaper.id == paper_id)
    )
    paper = result.scalar_one_or_none()

    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在")

    await db.execute(
        delete(ReadingPassage).where(ReadingPassage.paper_id == paper_id)
    )
    await db.delete(paper)
    await db.commit()

    return {"message": "删除成功"}
