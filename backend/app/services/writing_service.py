"""
作文服务

[INPUT]: 依赖 ai_service.py、models/writing.py
[OUTPUT]: 对外提供作文文体识别、范文生成、PDF 导出等服务
[POS]: backend/app/services 的作文业务逻辑层
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""
import re
import json
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.models.writing import (
    WritingTask,
    WritingTemplate,
    WritingSample,
    GRADE_OPTIONS,
    SEMESTER_OPTIONS,
    EXAM_TYPE_OPTIONS,
    WRITING_TYPE_OPTIONS,
)
from app.models.paper import ExamPaper
from app.services.ai_service import QwenService

logger = logging.getLogger(__name__)


# ==============================================================================
#                              CONSTANTS
# ==============================================================================

# 应用文子类型
APPLICATION_TYPES = {
    "书信": ["Dear", "Yours", "Best wishes", "Regards", "Sincerely"],
    "通知": ["Notice", "NOTICE", "通知"],
    "邀请": ["invite", "invitation", "邀请"],
    "日记": ["Monday", "Tuesday", "日记", "Date"],
    "邮件": ["Subject:", "To:", "From:", "@"],
}

# 应用文格式特征
APPLICATION_MARKERS = [
    r"Dear\s+\w+,",  # Dear xxx,
    r"Yours?\s+(sincerely|truly|faithfully)",  # Yours sincerely
    r"Best\s+wishes",  # Best wishes
    r"Regards,?",  # Regards
    r"Sincerely,?",  # Sincerely
]


class WritingService:
    """作文服务"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.ai_service = QwenService()

    # =========================================================================
    #                              文体识别
    # =========================================================================

    def detect_writing_type_by_rules(self, content: str) -> Tuple[str, Optional[str], float]:
        """
        基于规则判断文体类型

        Args:
            content: 作文内容

        Returns:
            (writing_type, application_type, confidence)
        """
        if not content or len(content.strip()) < 50:
            return "其他", None, 0.5

        # 检查应用文格式特征
        content_clean = content.strip()
        application_type = None

        for marker in APPLICATION_MARKERS:
            if re.search(marker, content_clean, re.IGNORECASE):
                # 尝试识别具体应用文类型
                for app_type, keywords in APPLICATION_TYPES.items():
                    for kw in keywords:
                        if kw.lower() in content_clean.lower():
                            application_type = app_type
                            break
                    if application_type:
                        break
                return "应用文", application_type, 0.9

        # 检查日记格式
        if re.search(r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+\w+", content_clean):
            return "应用文", "日记", 0.85

        # 默认为记叙文
        return "记叙文", None, 0.7

    async def detect_writing_type_with_ai(self, content: str) -> Dict:
        """
        使用 AI 判断文体类型（用于边界情况）

        Args:
            content: 作文内容

        Returns:
            {
                "writing_type": "应用文/记叙文/其他",
                "application_type": "书信/通知/...",
                "confidence": 0.95,
                "reasoning": "判断理由"
            }
        """
        content_preview = content[:1500] if len(content) > 1500 else content

        prompt = f"""
你是一位北京中考英语教研专家。请判断以下作文题目的文体类型。

作文题目：
{content_preview}

文体类型：
- 应用文：书信、通知、邀请、日记、邮件等有固定格式的文体
- 记叙文：讲述故事、描述经历、表达观点的文章
- 其他：无法归入以上两类的

判断标准：
- 如果开头有 Dear/To/Hi 等称呼，结尾有 Best wishes/Yours/Regards 等结束语，为应用文
- 如果有明显的日期开头（如 Monday, Date:），可能是日记
- 如果是讲述故事或描述经历，为记叙文

请按以下JSON格式输出（仅输出JSON）：
{{
    "writing_type": "应用文/记叙文/其他",
    "application_type": "书信/通知/邀请/日记/邮件/其他/null",
    "confidence": 0.95,
    "reasoning": "判断理由"
}}
"""

        try:
            response = self.ai_service.chat(prompt)
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return result
            return {
                "writing_type": "其他",
                "application_type": None,
                "confidence": 0.3,
                "reasoning": "AI 返回格式异常"
            }
        except Exception as e:
            logger.error(f"AI 文体识别失败: {e}")
            return {
                "writing_type": "其他",
                "application_type": None,
                "confidence": 0.3,
                "reasoning": f"AI 调用失败: {str(e)}"
            }

    async def detect_and_update_writing_type(self, task_id: int) -> Dict:
        """
        检测并更新作文文体类型

        Args:
            task_id: 作文 ID

        Returns:
            检测结果
        """
        # 获取作文
        result = await self.db.execute(
            select(WritingTask).where(WritingTask.id == task_id)
        )
        task = result.scalar_one_or_none()

        if not task:
            raise ValueError(f"作文不存在: {task_id}")

        content = task.task_content or ""

        # 先用规则判断
        writing_type, application_type, confidence = self.detect_writing_type_by_rules(content)

        # 如果置信度不高，用 AI 辅助判断
        if confidence < 0.8:
            ai_result = await self.detect_writing_type_with_ai(content)
            if ai_result.get("confidence", 0) > confidence:
                writing_type = ai_result.get("writing_type", "其他")
                application_type = ai_result.get("application_type")
                confidence = ai_result.get("confidence", 0)
                reasoning = ai_result.get("reasoning")
            else:
                reasoning = "规则判断"
        else:
            reasoning = "规则判断"

        # 更新数据库
        task.writing_type = writing_type
        task.application_type = application_type
        await self.db.commit()

        return {
            "task_id": task_id,
            "writing_type": writing_type,
            "application_type": application_type,
            "confidence": confidence,
            "reasoning": reasoning
        }

    # =========================================================================
    #                              范文生成
    # =========================================================================

    async def generate_sample(
        self,
        task_id: int,
        template_id: Optional[int] = None,
        score_level: str = "一档"
    ) -> WritingSample:
        """
        生成范文

        Args:
            task_id: 作文 ID
            template_id: 模板 ID（可选）
            score_level: 档次（一档/二档/三档）

        Returns:
            WritingSample
        """
        # 获取作文
        result = await self.db.execute(
            select(WritingTask).where(WritingTask.id == task_id)
        )
        task = result.scalar_one_or_none()

        if not task:
            raise ValueError(f"作文不存在: {task_id}")

        # 获取模板（如果有）
        template = None
        if template_id:
            result = await self.db.execute(
                select(WritingTemplate).where(WritingTemplate.id == template_id)
            )
            template = result.scalar_one_or_none()

        # 构建提示词
        content = task.task_content
        requirements = task.requirements or ""
        word_limit = task.word_limit or "80-100词"

        template_hint = ""
        if template:
            template_hint = f"""
参考模板：
{template.template_content}
"""

        prompt = f"""
你是一位北京中考英语教研专家，请根据以下作文题目生成一篇{score_level}范文。

作文题目：
{content}

要求：
{requirements}

字数要求：{word_limit}
{template_hint}

请生成一篇符合中考英语{score_level}作文评分标准的范文。
要求：
1. 语言地道、语法正确
2. 结构清晰、逻辑连贯
3. 使用高级词汇和句型
4. 符合字数要求

直接输出范文内容，不要其他解释。
"""

        try:
            sample_content = self.ai_service.chat(prompt)

            if not sample_content or len(sample_content.strip()) < 30:
                raise ValueError("AI 生成的范文内容太短")

            # 保存范文
            sample = WritingSample(
                task_id=task_id,
                template_id=template_id,
                sample_content=sample_content.strip(),
                sample_type="AI生成",
                score_level=score_level
            )
            self.db.add(sample)
            await self.db.commit()
            await self.db.refresh(sample)

            logger.info(f"范文生成成功: task_id={task_id}, score_level={score_level}")
            return sample

        except Exception as e:
            logger.error(f"范文生成失败: {e}")
            raise

    async def batch_generate_samples(
        self,
        task_ids: List[int],
        score_level: str = "一档"
    ) -> Dict:
        """
        批量生成范文（串行处理）

        Args:
            task_ids: 作文 ID 列表
            score_level: 档次

        Returns:
            {
                "success_count": 5,
                "fail_count": 1,
                "results": [...]
            }
        """
        success_count = 0
        fail_count = 0
        results = []

        for task_id in task_ids:
            try:
                sample = await self.generate_sample(task_id, score_level=score_level)
                success_count += 1
                results.append({
                    "task_id": task_id,
                    "success": True,
                    "sample_id": sample.id
                })
                logger.info(f"批量生成进度: {success_count}/{len(task_ids)}")
            except Exception as e:
                fail_count += 1
                results.append({
                    "task_id": task_id,
                    "success": False,
                    "error": str(e)
                })
                logger.warning(f"批量生成失败: task_id={task_id}, error={e}")

        return {
            "success_count": success_count,
            "fail_count": fail_count,
            "results": results
        }

    # =========================================================================
    #                              模板管理
    # =========================================================================

    async def get_or_create_template(
        self,
        writing_type: str,
        application_type: Optional[str] = None
    ) -> WritingTemplate:
        """
        获取或创建模板

        Args:
            writing_type: 文体类型
            application_type: 应用文子类型

        Returns:
            WritingTemplate
        """
        # 查找现有模板
        query = select(WritingTemplate).where(
            WritingTemplate.writing_type == writing_type
        )
        if application_type:
            query = query.where(WritingTemplate.application_type == application_type)

        result = await self.db.execute(query.limit(1))
        template = result.scalar_one_or_none()

        if template:
            return template

        # 生成新模板
        template_data = self.ai_service.generate_writing_template(writing_type, application_type)

        template = WritingTemplate(
            writing_type=writing_type,
            application_type=application_type,
            template_name=template_data.get("template_name", f"{writing_type}模板"),
            template_content=template_data.get("template_content", ""),
            tips="\n".join(template_data.get("tips", [])),
            structure=template_data.get("structure", "")
        )

        self.db.add(template)
        await self.db.commit()
        await self.db.refresh(template)

        return template

    # =========================================================================
    #                              查询方法
    # =========================================================================

    async def get_writings(
        self,
        page: int = 1,
        size: int = 20,
        grade: Optional[str] = None,
        semester: Optional[str] = None,
        exam_type: Optional[str] = None,
        writing_type: Optional[str] = None,
        application_type: Optional[str] = None,
        topic: Optional[str] = None,
        search: Optional[str] = None
    ) -> Tuple[List[WritingTask], int, Dict]:
        """
        获取作文列表

        Returns:
            (items, total, grade_counts)
        """
        query = select(WritingTask).options(
            selectinload(WritingTask.paper)
        )

        # 筛选条件
        if grade:
            query = query.where(WritingTask.grade == grade)
        if semester:
            query = query.where(WritingTask.semester == semester)
        if exam_type:
            query = query.where(WritingTask.exam_type == exam_type)
        if writing_type:
            query = query.where(WritingTask.writing_type == writing_type)
        if application_type:
            query = query.where(WritingTask.application_type == application_type)
        if topic:
            query = query.where(WritingTask.primary_topic == topic)
        if search:
            query = query.where(WritingTask.task_content.contains(search))

        # 统计总数
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # 分页
        query = query.order_by(WritingTask.created_at.desc())
        query = query.offset((page - 1) * size).limit(size)

        result = await self.db.execute(query)
        items = list(result.scalars().all())

        # 统计各年级数量
        grade_counts = {}
        for g in GRADE_OPTIONS:
            count_query = select(func.count()).select_from(
                WritingTask.__table__
            ).where(WritingTask.grade == g)
            count_result = await self.db.execute(count_query)
            grade_counts[g] = count_result.scalar() or 0

        return items, total, grade_counts

    async def get_writing_detail(self, task_id: int) -> Optional[WritingTask]:
        """
        获取作文详情（含模板和范文）
        """
        query = select(WritingTask).options(
            selectinload(WritingTask.paper),
            selectinload(WritingTask.samples)
        ).where(WritingTask.id == task_id)

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_filters(self) -> Dict:
        """
        获取筛选项
        """
        # 年级
        grades_result = await self.db.execute(
            select(WritingTask.grade).distinct().where(
                WritingTask.grade.isnot(None)
            )
        )
        grades = [g for g in grades_result.scalars().all() if g]

        # 学期
        semesters_result = await self.db.execute(
            select(WritingTask.semester).distinct().where(
                WritingTask.semester.isnot(None)
            )
        )
        semesters = [s for s in semesters_result.scalars().all() if s]

        # 考试类型
        exam_types_result = await self.db.execute(
            select(WritingTask.exam_type).distinct().where(
                WritingTask.exam_type.isnot(None)
            )
        )
        exam_types = [e for e in exam_types_result.scalars().all() if e]

        # 文体类型
        writing_types_result = await self.db.execute(
            select(WritingTask.writing_type).distinct().where(
                WritingTask.writing_type.isnot(None)
            )
        )
        writing_types = [w for w in writing_types_result.scalars().all() if w]

        # 应用文子类型
        application_types_result = await self.db.execute(
            select(WritingTask.application_type).distinct().where(
                WritingTask.application_type.isnot(None)
            )
        )
        application_types = [a for a in application_types_result.scalars().all() if a]

        # 话题
        topics_result = await self.db.execute(
            select(WritingTask.primary_topic).distinct().where(
                WritingTask.primary_topic.isnot(None)
            )
        )
        topics = [t for t in topics_result.scalars().all() if t]

        return {
            "grades": sorted(grades),
            "semesters": sorted(semesters),
            "exam_types": sorted(exam_types),
            "writing_types": sorted(writing_types),
            "application_types": sorted(application_types),
            "topics": sorted(topics)
        }
