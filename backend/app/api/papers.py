"""
试卷管理API

可扩展的步骤化处理流程
"""
import os
import re
import json
import asyncio
import logging
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
from app.services.text_utils import normalize_cloze_blanks, align_blank_numbers_with_content


def count_english_words(text: str) -> int:
    """精确计算英文词数（只匹配英文字母组成的单词）"""
    if not text:
        return 0
    # 匹配连续的英文字母（包括带连字符的单词）
    words = re.findall(r"[a-zA-Z]+(?:-[a-zA-Z]+)*", text)
    return len(words)


def strip_image_tokens(text: str) -> str:
    """移除题干中的图片 token，避免影响后续 AI 解析。"""
    if not text:
        return ""
    return re.sub(r"\s*\[IMAGE(?::[^\]]+)?\]", "", text).strip()


from app.models.paper import ExamPaper
from app.models.reading import ReadingPassage, Question
from app.models.vocabulary import Vocabulary, VocabularyPassage
from app.models.cloze import ClozePassage, ClozePoint, ClozeSecondaryPoint, ClozeRejectionPoint
from app.models.vocabulary_cloze import VocabularyCloze
from app.models.writing import WritingTask
from app.schemas.paper import PaperCreate, PaperResponse, PaperListResponse
from app.services.docx_parser import DocxParser
from app.services.llm_parser import LLMDocumentParser, WritingExtractResult
from app.services.topic_classifier import TopicClassifier
from app.services.writing_topic_classifier import WritingTopicClassifier
from app.services.vocab_extractor import VocabExtractor
from app.services.cloze_analyzer import ClozeAnalyzerV5, NEW_CODE_TO_LEGACY
from app.services.image_extractor import ImageExtractor

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================================================
#  选项验证和重试机制
# ============================================================================

def validate_question_options(question_data: dict) -> tuple[bool, str]:
    """
    验证题目选项是否有效（至少有一个非空选项）

    注意：
    - 有些题目只有3个选项，不能强制要求4个
    - 有些阅读题是开放题，本身就没有 A/B/C/D 选项
    - 图片选项使用 [IMAGE] 占位符或 [IMAGE:...] 格式
    - 有 has_image_options 标记的题目，选项可以为 [IMAGE]

    Returns:
        (is_valid, error_message)
    """
    options = question_data.get("options", {})

    # 开放题没有 A/B/C/D 选项，跳过选项校验
    if question_data.get("is_open_ended"):
        return True, ""

    # 如果标记为有图片选项，跳过验证
    if question_data.get("has_image_options"):
        # 检查是否有 [IMAGE] 占位符
        has_image_placeholder = any(
            options.get(opt) in ["[IMAGE]", ""] or
            (options.get(opt) and options.get(opt).startswith("[IMAGE:"))
            for opt in ['A', 'B', 'C', 'D']
        )
        if has_image_placeholder:
            return True, ""
        # 即使没有占位符，也允许（可能是 LLM 没正确标记）
        return True, ""

    # 检查是否有至少一个有效的非空选项（文本或图片引用）
    has_valid_option = False
    for opt in ['A', 'B', 'C', 'D']:
        opt_val = options.get(opt, '')
        if opt_val:
            opt_val = opt_val.strip()
            # 文本选项 或 图片引用
            if opt_val and opt_val != '[IMAGE]':
                has_valid_option = True
                break
            # [IMAGE:...] 格式的图片引用也算有效
            if opt_val.startswith('[IMAGE:'):
                has_valid_option = True
                break

    if not has_valid_option:
        return False, f"题目 {question_data.get('question_number', '?')} 所有选项均为空"
    return True, ""


def validate_llm_result_options(llm_result) -> tuple[bool, list]:
    """
    验证LLM解析结果中所有题目的选项

    Returns:
        (is_valid, list_of_errors)
    """
    if not llm_result.success:
        return False, ["LLM解析失败"]

    errors = []
    for passage in (llm_result.passages or []):
        passage_type = passage.get("passage_type", "?")
        for q in passage.get("questions", []):
            is_valid, error = validate_question_options(q)
            if not is_valid:
                errors.append(f"{passage_type}篇 - {error}")

    return len(errors) == 0, errors


# AI解析最大重试次数
MAX_AI_RETRIES = 3


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
    {"id": "generate_explanations", "name": "生成解析", "description": "AI生成答案解析", "icon": "💡"},
    {"id": "save_cloze", "name": "保存完形填空", "description": "提取并保存完形文章", "icon": "📝"},
    {"id": "writing_extract", "name": "作文提取", "description": "从试卷中提取作文题目", "icon": "✍️"},
    {"id": "cloze_analyze", "name": "考点分析", "description": "AI分析四类考点", "icon": "🔬"},
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
                                       "save_questions", "save_cloze", "writing_extract",
                                       "cloze_analyze", "topic_classify", "vocab_extract"]:
                            reporter.skip_step(step_id, "试卷已存在")
                        yield emit()
                        return
                    # 强制模式：先删除关联记录，再删除主记录
                    # 1. 删除阅读文章的词汇关联
                    reading_ids = await db.execute(
                        select(ReadingPassage.id).where(ReadingPassage.paper_id == existing_paper.id)
                    )
                    reading_id_list = [r[0] for r in reading_ids.all()]
                    if reading_id_list:
                        await db.execute(
                            delete(VocabularyPassage).where(VocabularyPassage.passage_id.in_(reading_id_list))
                        )
                        await db.execute(
                            delete(Question).where(Question.passage_id.in_(reading_id_list))
                        )
                    # 2. 删除完形文章的词汇关联
                    cloze_ids = await db.execute(
                        select(ClozePassage.id).where(ClozePassage.paper_id == existing_paper.id)
                    )
                    cloze_id_list = [c[0] for c in cloze_ids.all()]
                    if cloze_id_list:
                        # 先获取所有 ClozePoint 的 ID，用于删除子表数据
                        cloze_point_ids = await db.execute(
                            select(ClozePoint.id).where(ClozePoint.cloze_id.in_(cloze_id_list))
                        )
                        cloze_point_id_list = [p[0] for p in cloze_point_ids.all()]

                        if cloze_point_id_list:
                            # 删除辅助考点
                            await db.execute(
                                delete(ClozeSecondaryPoint).where(ClozeSecondaryPoint.cloze_point_id.in_(cloze_point_id_list))
                            )
                            # 删除排错点
                            await db.execute(
                                delete(ClozeRejectionPoint).where(ClozeRejectionPoint.cloze_point_id.in_(cloze_point_id_list))
                            )

                        # 删除词汇关联
                        await db.execute(
                            delete(VocabularyCloze).where(VocabularyCloze.cloze_id.in_(cloze_id_list))
                        )
                        # 删除考点主表
                        await db.execute(
                            delete(ClozePoint).where(ClozePoint.cloze_id.in_(cloze_id_list))
                        )
                    # 3. 删除文章和完形
                    await db.execute(
                        delete(ReadingPassage).where(ReadingPassage.paper_id == existing_paper.id)
                    )
                    await db.execute(
                        delete(ClozePassage).where(ClozePassage.paper_id == existing_paper.id)
                    )
                    # 4. 删除试卷
                    await db.delete(existing_paper)
                    await db.flush()

                # 创建试卷记录
                paper = ExamPaper(
                    filename=file.filename,
                    original_path=tmp_path,
                    year=metadata.get("year"),
                    region=metadata.get("region"),
                    school=metadata.get("school"),  # 学校名（如果有）
                    grade=metadata.get("grade"),
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
                    paper.import_status = "failed"
                    paper.error_message = str(e)
                    await db.commit()
                    reporter.fail_step("upload_to_ai", str(e))
                    yield emit()
                    return

                # ===== Step 4: AI解析文档（带重试机制） =====
                reporter.start_step("ai_parse", "🤖 AI正在解析文档...")
                yield emit()

                llm_result = None
                last_error = ""
                image_extractor = ImageExtractor()

                try:
                    for retry_attempt in range(MAX_AI_RETRIES):
                        # 更新进度消息
                        attempt_msg = f"提取试卷结构... (尝试 {retry_attempt + 1}/{MAX_AI_RETRIES})"
                        reporter.update_step("ai_parse", message=attempt_msg, progress=20 + retry_attempt * 10)
                        yield emit()

                        llm_result = await llm_parser.parse_document_with_fileid(fileid, file_path=tmp_path)

                        if not llm_result.success:
                            last_error = llm_result.error or "解析失败"
                            logger.warning(f"AI解析失败 (尝试 {retry_attempt + 1}/{MAX_AI_RETRIES}): {last_error}")
                            continue

                        # 先基于题目块回填图片选项，再做选项有效性校验
                        try:
                            option_images, warnings = image_extractor.enrich_passages_with_images(
                                doc_path=tmp_path,
                                paper_id=paper.id,
                                passages=llm_result.passages,
                            )
                            for warning in warnings:
                                logger.warning(warning)
                            if option_images:
                                logger.info(f"提取了 {len(option_images)} 张选项图片")
                        except Exception as image_error:
                            logger.warning(f"图片提取失败（不影响导入）: {image_error}")

                        # 验证选项是否有效
                        is_valid, errors = validate_llm_result_options(llm_result)
                        if not is_valid:
                            last_error = "; ".join(errors)
                            logger.warning(f"选项验证失败 (尝试 {retry_attempt + 1}/{MAX_AI_RETRIES}): {last_error}")
                            continue

                        # 解析成功且选项有效
                        break

                    # 检查最终结果
                    if not llm_result or not llm_result.success:
                        paper.import_status = "failed"
                        paper.error_message = last_error
                        await db.commit()
                        reporter.fail_step("ai_parse", f"经过{MAX_AI_RETRIES}次重试仍失败: {last_error}")
                        yield emit()
                        return

                    # 检查是否有选项为空的警告（但不阻止流程）
                    is_valid, errors = validate_llm_result_options(llm_result)
                    if not is_valid:
                        logger.warning(f"部分题目选项为空（将正常保存）: {'; '.join(errors)}")

                    passages_count = len(llm_result.passages)
                    questions_count = sum(len(p.get("questions", [])) for p in llm_result.passages)

                    reporter.complete_step(
                        "ai_parse",
                        f"提取{passages_count}篇文章, {questions_count}道题目",
                        data={"passages": passages_count, "questions": questions_count}
                    )
                    yield emit()

                except Exception as e:
                    paper.import_status = "failed"
                    paper.error_message = str(e)
                    await db.commit()
                    reporter.fail_step("ai_parse", str(e))
                    yield emit()
                    return

                # 先仅写入解析策略，试卷状态保持 processing，直到整条流水线完成。
                paper.parse_strategy = "llm"
                paper.confidence = 0.95

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
                await db.commit()
                yield emit()

                # ===== Step 6: 保存题目 =====
                reporter.start_step("save_questions", "正在保存题目...")
                yield emit()

                questions_created = 0
                saved_questions = []  # 保存题目对象用于后续生成解析
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
                            saved_questions.append((question, passage.content))
                            questions_created += 1

                reporter.complete_step("save_questions", f"已保存{questions_created}道题目")
                await db.commit()
                yield emit()

                # ===== Step 6.5: AI生成答案解析 =====
                if saved_questions:
                    reporter.start_step("generate_explanations", "AI正在生成答案解析...")
                    yield emit()

                    from app.services.ai_service import QwenService
                    ai_service = QwenService()

                    explanations_generated = 0
                    for idx, (question, passage_content) in enumerate(saved_questions):
                        reporter.update_step("generate_explanations",
                            progress=int((idx + 1) / len(saved_questions) * 100),
                            message=f"优化第{question.question_number}题答案解析..."
                        )
                        yield emit()

                        # 构建选项字典（过滤图片选项）
                        options_dict = {}
                        for opt_key, opt_val in [
                            ("A", question.option_a),
                            ("B", question.option_b),
                            ("C", question.option_c),
                            ("D", question.option_d)
                        ]:
                            if not opt_val:
                                continue
                            if opt_val.startswith("[IMAGE:"):
                                continue
                            options_dict[opt_key] = opt_val

                        existing_explanation = (question.answer_explanation or "").strip()

                        # 调用AI优化/补全解析。即使原题已有答案或解析，也继续增强。
                        try:
                            explanation = ai_service.generate_answer_explanation(
                                question_text=strip_image_tokens(question.question_text),
                                options=options_dict,
                                correct_answer=question.correct_answer or "",
                                passage_content=passage_content,
                                existing_explanation=existing_explanation,
                            )
                            if explanation:
                                question.answer_explanation = explanation
                                explanations_generated += 1
                            elif existing_explanation:
                                question.answer_explanation = existing_explanation
                        except Exception as e:
                            logger.warning(f"生成第{question.question_number}题解析失败: {e}")
                            if existing_explanation:
                                question.answer_explanation = existing_explanation

                    reporter.complete_step("generate_explanations", f"已生成{explanations_generated}条解析")
                    await db.commit()
                    yield emit()

                # ===== Step 7: 保存完形填空 =====
                reporter.start_step("save_cloze", "正在提取完形填空...")
                yield emit()

                cloze_created = False
                cloze_passage = None
                blanks_created = 0

                if llm_result.cloze and llm_result.cloze.get("found"):
                    cloze_data = llm_result.cloze

                    # 标准化空格格式
                    cloze_content = cloze_data.get("content_with_blanks", "")
                    blanks_count = len(cloze_data.get("blanks", []))
                    normalized_content = await normalize_cloze_blanks(cloze_content, blanks_count)

                    # 创建完形文章
                    cloze_passage = ClozePassage(
                        paper_id=paper.id,
                        content=normalized_content,
                        original_content=cloze_data.get("content_full"),
                        word_count=cloze_data.get("word_count", 0)
                    )
                    db.add(cloze_passage)
                    await db.flush()

                    # 保存空格
                    blanks_data = cloze_data.get("blanks", [])
                    aligned_blank_numbers = align_blank_numbers_with_content(
                        normalized_content,
                        [blank_data.get("blank_number") or 0 for blank_data in blanks_data],
                    )

                    for blank_index, blank_data in enumerate(blanks_data):
                        options = blank_data.get("options", {})
                        point = ClozePoint(
                            cloze_id=cloze_passage.id,
                            blank_number=aligned_blank_numbers[blank_index] if blank_index < len(aligned_blank_numbers) else blank_data.get("blank_number"),
                            correct_answer=blank_data.get("correct_answer"),
                            options=json.dumps(options, ensure_ascii=False),
                            correct_word=blank_data.get("correct_word")
                        )
                        db.add(point)
                        blanks_created += 1

                    # 刷新以确保空格记录在数据库中可用
                    await db.flush()

                    cloze_created = True
                    reporter.complete_step("save_cloze", f"已提取{blanks_created}个空格")
                    await db.commit()
                else:
                    reporter.skip_step("save_cloze", "未找到完形填空")
                yield emit()

                # ===== Step: 作文提取 =====
                reporter.start_step("writing_extract", "✍️ AI 正在提取作文题目...")
                yield emit()

                writing_created = False
                try:
                    # 使用 LLM 提取作文（替代正则表达式）
                    writing_result = await llm_parser.extract_writing(fileid, file_path=tmp_path)

                    if writing_result.success and writing_result.content:
                        # ===== 新增：话题提取 =====
                        primary_topic = None
                        try:
                            topic_classifier = WritingTopicClassifier()
                            # 使用同步方法（在线程池中运行避免阻塞）
                            topic_result = await asyncio.to_thread(
                                topic_classifier.classify_sync,
                                content=writing_result.content,
                                requirements=writing_result.requirements or ""
                            )
                            if topic_result.success:
                                primary_topic = topic_result.primary_topic
                        except Exception as topic_error:
                            logger.warning(f"话题提取失败（不影响导入）: {topic_error}")

                        # 创建作文题目记录（包含文体类型和话题）
                        writing_task = WritingTask(
                            paper_id=paper.id,
                            task_content=writing_result.content,
                            requirements=writing_result.requirements,
                            word_limit=writing_result.word_limit,
                            writing_type=writing_result.writing_type,
                            application_type=writing_result.application_type,
                            primary_topic=primary_topic,  # 新增
                            grade=metadata.get("grade"),
                            semester=metadata.get("semester"),
                            exam_type=metadata.get("exam_type")
                        )
                        db.add(writing_task)
                        await db.flush()

                        # ===== 自动生成范文 =====
                        try:
                            from app.services.writing_service import WritingService
                            writing_service = WritingService(db)
                            sample = await writing_service.generate_sample(
                                task_id=writing_task.id,
                                score_level="一档"
                            )
                            logger.info(f"自动生成范文成功: sample_id={sample.id}")
                        except Exception as sample_error:
                            logger.warning(f"自动生成范文失败（不影响导入）: {sample_error}")

                        writing_created = True
                        type_info = writing_result.writing_type
                        if writing_result.application_type:
                            type_info += f"({writing_result.application_type})"
                        topic_info = f" | 话题: {primary_topic}" if primary_topic else ""
                        reporter.complete_step("writing_extract", f"已提取: {type_info}{topic_info}")
                        await db.commit()
                    else:
                        reporter.skip_step("writing_extract", writing_result.error or "未找到作文题目")
                except Exception as e:
                    reporter.skip_step("writing_extract", f"跳过: {str(e)}")
                yield emit()

                # ===== Step 8: 考点分析 =====
                if cloze_created:
                    reporter.start_step("cloze_analyze", "🔬 AI正在分析考点...")
                    yield emit()

                    try:
                        analyzer = ClozeAnalyzerV5()  # 使用 V5 分析器（全信号扫描 + 动态维度）
                        analyzed_count = 0

                        # 获取刚创建的空格列表
                        result = await db.execute(
                            select(ClozePoint).where(ClozePoint.cloze_id == cloze_passage.id)
                        )
                        points = result.scalars().all()

                        for i, point in enumerate(points):
                            if point.correct_word and point.options:
                                reporter.update_step("cloze_analyze",
                                    progress=int((i + 1) / len(points) * 100),
                                    message=f"分析第{point.blank_number}空...")
                                yield emit()

                                # 解析选项
                                options = json.loads(point.options) if isinstance(point.options, str) else point.options

                                # 提取上下文
                                context = analyzer.extract_context(
                                    cloze_passage.content,
                                    point.blank_number
                                )

                                # AI分析考点（传入 db_session 支持课本释义查询）
                                analysis_result = await analyzer.analyze_point(
                                    blank_number=point.blank_number,
                                    correct_word=point.correct_word,
                                    options=options,
                                    context=context,
                                    db_session=db  # 支持课本单词表查询
                                )

                                if analysis_result.success:
                                    # === V2 考点分类系统 ===
                                    # 保存主考点编码
                                    if analysis_result.primary_point:
                                        point.primary_point_code = analysis_result.primary_point.get("code")
                                        # 向后兼容：映射到旧类型
                                        if point.primary_point_code in NEW_CODE_TO_LEGACY:
                                            point.point_type = NEW_CODE_TO_LEGACY[point.primary_point_code]
                                            point.legacy_point_type = point.point_type

                                    # 基础字段
                                    point.translation = analysis_result.translation
                                    point.explanation = analysis_result.explanation
                                    point.sentence = context  # 保存上下文句子

                                    # 易混淆词
                                    if analysis_result.confusion_words:
                                        point.confusion_words = json.dumps(
                                            analysis_result.confusion_words, ensure_ascii=False
                                        )

                                    # 通用字段
                                    if analysis_result.tips:
                                        point.tips = analysis_result.tips

                                    # 固定搭配专用
                                    if analysis_result.phrase:
                                        point.phrase = analysis_result.phrase
                                    if analysis_result.similar_phrases:
                                        point.similar_phrases = json.dumps(
                                            analysis_result.similar_phrases, ensure_ascii=False
                                        )

                                    # 词义辨析专用
                                    if analysis_result.word_analysis:
                                        point.word_analysis = json.dumps(
                                            analysis_result.word_analysis, ensure_ascii=False
                                        )
                                    if analysis_result.dictionary_source:
                                        point.dictionary_source = analysis_result.dictionary_source

                                    # 熟词僻义专用（作为附加标签）
                                    if analysis_result.is_rare_meaning:
                                        point.is_rare_meaning = True
                                    if analysis_result.textbook_meaning:
                                        point.textbook_meaning = analysis_result.textbook_meaning
                                    if analysis_result.textbook_source:
                                        point.textbook_source = analysis_result.textbook_source
                                    if analysis_result.context_meaning:
                                        point.context_meaning = analysis_result.context_meaning
                                    if analysis_result.similar_words:
                                        point.similar_words = json.dumps(
                                            analysis_result.similar_words, ensure_ascii=False
                                        )

                                    # 保存辅助考点（V2 多标签）
                                    if analysis_result.secondary_points:
                                        for idx, sp in enumerate(analysis_result.secondary_points):
                                            point_code = sp.get("code") or sp.get("point_code") or "D1"
                                            sec_point = ClozeSecondaryPoint(
                                                cloze_point_id=point.id,
                                                point_code=point_code,
                                                explanation=sp.get("explanation"),
                                                sort_order=idx
                                            )
                                            db.add(sec_point)

                                    # 保存排错点（V5 字段：rejection_code / rejection_reason）
                                    if analysis_result.rejection_points:
                                        for rp in analysis_result.rejection_points:
                                            # 优先取 rejection_code，fallback 到 code/point_code
                                            rejection_code = rp.get("rejection_code") or rp.get("code") or rp.get("point_code") or "D1"
                                            # 优先取 rejection_reason，fallback 到 explanation
                                            rejection_reason = rp.get("rejection_reason") or rp.get("explanation") or ""
                                            rej_point = ClozeRejectionPoint(
                                                cloze_point_id=point.id,
                                                option_word=rp.get("option_word"),
                                                point_code=rejection_code,
                                                rejection_code=rejection_code,
                                                explanation=rejection_reason,
                                                rejection_reason=rejection_reason
                                            )
                                            db.add(rej_point)

                                    analyzed_count += 1
                                else:
                                    pass  # 分析失败，不更新

                        reporter.complete_step("cloze_analyze", f"已分析{analyzed_count}个考点")
                        await db.commit()
                        yield emit()

                    except Exception as e:
                        reporter.skip_step("cloze_analyze", f"跳过: {str(e)}")
                        yield emit()
                else:
                    reporter.skip_step("cloze_analyze", "无完形文章")
                    yield emit()

                # ===== Step 9: AI话题分类 =====
                reporter.start_step("topic_classify", "🎯 AI正在提炼主题...")
                yield emit()

                try:
                    classifier = TopicClassifier()
                    topics_found = []

                    # 阅读文章话题分类
                    for i, passage in enumerate(saved_passages):
                        if passage.content and len(passage.content) > 50:
                            reporter.update_step("topic_classify",
                                progress=int((i + 1) / (len(saved_passages) + (1 if cloze_created else 0)) * 50),
                                message=f"分析{passage.passage_type}篇主题...")
                            yield emit()

                            topic_result = await classifier.classify(passage.content, paper.grade or "初二")
                            if topic_result.success and topic_result.primary_topic:
                                passage.primary_topic = topic_result.primary_topic
                                passage.secondary_topics = json.dumps([], ensure_ascii=False)  # 不再使用次要话题
                                passage.topic_confidence = topic_result.confidence
                                if topic_result.keywords:
                                    passage.keywords = json.dumps(topic_result.keywords, ensure_ascii=False)
                                topics_found.append(topic_result.primary_topic)

                    # 完形文章话题分类
                    if cloze_created and cloze_passage.original_content:
                        reporter.update_step("topic_classify", progress=75, message="分析完形文章主题...")
                        yield emit()

                        topic_result = await classifier.classify(cloze_passage.original_content, paper.grade or "初二")
                        if topic_result.success and topic_result.primary_topic:
                            cloze_passage.primary_topic = topic_result.primary_topic
                            cloze_passage.secondary_topics = json.dumps([], ensure_ascii=False)  # 不再使用次要话题
                            cloze_passage.topic_confidence = topic_result.confidence
                            topics_found.append(topic_result.primary_topic)

                    reporter.complete_step("topic_classify", f"已分类{len(topics_found)}篇文章主题")
                    await db.commit()
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

                            existing_passage_keys = await db.execute(
                                select(
                                    VocabularyPassage.vocabulary_id,
                                    VocabularyPassage.char_position
                                ).where(VocabularyPassage.passage_id == passage.id)
                            )
                            seen_passage_occurrences = {
                                (row[0], row[1]) for row in existing_passage_keys.all()
                            }

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
                                    occ_key = (vocab.id, occ.char_position)
                                    if occ_key in seen_passage_occurrences:
                                        continue

                                    vocab_passage = VocabularyPassage(
                                        vocabulary_id=vocab.id,
                                        passage_id=passage.id,
                                        sentence=occ.sentence,
                                        char_position=occ.char_position,
                                        end_position=occ.end_position,
                                        word_position=occ.word_position
                                    )
                                    db.add(vocab_passage)
                                    seen_passage_occurrences.add(occ_key)
                                    total_words += 1

                    # 完形文章词汇提取
                    # 注意：使用 content（带空格标记），而非 original_content
                    # 这样 char_position 与前端渲染的文本位置一致
                    if cloze_created and cloze_passage:
                        content_for_vocab = cloze_passage.content
                        if content_for_vocab and len(content_for_vocab) > 50:
                            reporter.update_step("vocab_extract", progress=75, message="AI分析完形文章核心词汇...")
                            yield emit()

                            # 使用AI异步提取
                            extracted_words = await vocab_extractor.extract_async(content_for_vocab)

                            existing_cloze_keys = await db.execute(
                                select(
                                    VocabularyCloze.vocabulary_id,
                                    VocabularyCloze.char_position
                                ).where(VocabularyCloze.cloze_id == cloze_passage.id)
                            )
                            seen_cloze_occurrences = {
                                (row[0], row[1]) for row in existing_cloze_keys.all()
                            }

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
                                        frequency=0,
                                        definition=word_data.definition
                                    )
                                    db.add(vocab)
                                    await db.flush()
                                else:
                                    if not vocab.definition and word_data.definition:
                                        vocab.definition = word_data.definition

                                # 创建完形词汇关联记录
                                for occ in word_data.occurrences:
                                    occ_key = (vocab.id, occ.char_position)
                                    if occ_key in seen_cloze_occurrences:
                                        continue

                                    vocab_cloze = VocabularyCloze(
                                        vocabulary_id=vocab.id,
                                        cloze_id=cloze_passage.id,
                                        sentence=occ.sentence,
                                        char_position=occ.char_position,
                                        end_position=occ.end_position,
                                        word_position=occ.word_position
                                    )
                                    db.add(vocab_cloze)
                                    seen_cloze_occurrences.add(occ_key)
                                    total_words += 1

                    # 在发送“词汇提取完成”进度前先提交，避免客户端提前断开时丢失尾段结果
                    await db.commit()

                    reporter.complete_step("vocab_extract", f"AI已提取{total_words}个核心词汇")
                    yield emit()

                except Exception as e:
                    reporter.skip_step("vocab_extract", f"跳过: {str(e)}")
                    yield emit()

                # 所有后处理完成后，才将试卷标记为 completed。
                paper.import_status = "completed"
                paper.error_message = None
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
    """删除试卷及其所有关联数据"""
    result = await db.execute(
        select(ExamPaper).where(ExamPaper.id == paper_id)
    )
    paper = result.scalar_one_or_none()

    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在")

    # 1. 删除阅读文章的词汇关联和题目
    reading_ids = await db.execute(
        select(ReadingPassage.id).where(ReadingPassage.paper_id == paper_id)
    )
    reading_id_list = [r[0] for r in reading_ids.all()]
    if reading_id_list:
        await db.execute(
            delete(VocabularyPassage).where(VocabularyPassage.passage_id.in_(reading_id_list))
        )
        await db.execute(
            delete(Question).where(Question.passage_id.in_(reading_id_list))
        )

    # 2. 删除完形文章的词汇关联和考点
    cloze_ids = await db.execute(
        select(ClozePassage.id).where(ClozePassage.paper_id == paper_id)
    )
    cloze_id_list = [c[0] for c in cloze_ids.all()]
    if cloze_id_list:
        await db.execute(
            delete(VocabularyCloze).where(VocabularyCloze.cloze_id.in_(cloze_id_list))
        )
        await db.execute(
            delete(ClozePoint).where(ClozePoint.cloze_id.in_(cloze_id_list))
        )

    # 3. 删除文章和完形
    await db.execute(
        delete(ReadingPassage).where(ReadingPassage.paper_id == paper_id)
    )
    await db.execute(
        delete(ClozePassage).where(ClozePassage.paper_id == paper_id)
    )

    # 4. 删除试卷
    await db.delete(paper)
    await db.commit()

    return {"message": "删除成功"}
